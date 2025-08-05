from celery import Celery
from flask import current_app
import pandas as pd
import os
import logging
from datetime import datetime
from bson.objectid import ObjectId
import numpy as np

from app.ml.dataset_manager import load_and_prepare_student_data
from app.ml.trainer import train_dropout_models

logger = logging.getLogger(__name__)

celery_app = Celery('edflow_tasks')

@celery_app.task(bind=True)
def process_uploaded_data_and_train_model(self, file_path, model_name, user_id_str, is_paid):
    try:
        logger.info(f"Starting Celery task: process_uploaded_data_and_train_model for {model_name}")

        df_uploaded = pd.read_csv(file_path)
        logger.info(f"Read {len(df_uploaded)} rows from uploaded CSV: {file_path}")

        db = current_app.db
        students_col = db.students

        csv_to_mongo_mapping = {
            'student ID': 'student_id',
            'age': 'age',
            'gender': 'gender',
            'highSchoolGPA': 'highSchoolGPA',
            'currentGPA': 'currentGPA',
            'study_hours': 'study_hours',
            'social_media_hours': 'social_media_hours',
            'netflix_hours': 'netflix_hours',
            'part_time_job': 'part_time_job',
            'attendance': 'attendance',
            'sleep_hours': 'sleep_hours',
            'diet_quality': 'diet_quality',
            'exercise_frequency': 'exercise_frequency',
            'parental_education': 'parental_education',
            'internet_quality': 'internet_quality',
            'mental_health_score': 'mental_health_score',
            'extracurricular_activities': 'extracurricular_activities',
            'exam_score': 'exam_score',
            'dropout': 'dropout'
        }

        numerical_cols_csv = [
            'age', 'study_hours', 'social_media_hours', 'netflix_hours', 'attendance', 'sleep_hours',
            'mental_health_score', 'exam_score', 'highSchoolGPA', 'currentGPA'
        ]
        boolean_cols_csv = ['part_time_job', 'extracurricular_activities']

        ingested_count = 0

        for index, row in df_uploaded.iterrows():
            student_doc = {}
            ml_features_doc = {}

            student_id_val = row.get('student ID')
            if pd.isna(student_id_val) or str(student_id_val).strip() == '':
                logger.warning(f"Skipping row {index} due to missing or empty 'student ID'. Row data: {row.to_dict()}")
                continue
            student_doc['student_id'] = str(student_id_val).strip()

            student_doc['gender'] = row.get('gender') if pd.notna(row.get('gender')) else None

            for col_name in ['highSchoolGPA', 'currentGPA']:
                gpa_value = row.get(col_name)
                try:
                    student_doc[col_name] = float(gpa_value) if pd.notna(gpa_value) else None
                except Exception:
                    student_doc[col_name] = None

            for csv_col, mongo_field in csv_to_mongo_mapping.items():
                if mongo_field in ['student_id', 'age', 'gender', 'highSchoolGPA', 'currentGPA', 'dropout']:
                    continue
                val = row.get(csv_col)
                if pd.isna(val):
                    ml_features_doc[mongo_field] = None
                elif csv_col in numerical_cols_csv:
                    try:
                        ml_features_doc[mongo_field] = float(val)
                    except Exception:
                        ml_features_doc[mongo_field] = None
                elif csv_col in boolean_cols_csv:
                    ml_features_doc[mongo_field] = str(val).lower() in ['true', 'yes', '1']
                else:
                    ml_features_doc[mongo_field] = str(val)

            student_doc['ml_features'] = ml_features_doc

            dropout_val = row.get('dropout')
            if pd.notna(dropout_val):
                if isinstance(dropout_val, (int, float)):
                    student_doc['dropout'] = bool(int(dropout_val))
                elif isinstance(dropout_val, str):
                    student_doc['dropout'] = dropout_val.lower() in ['true', 'yes', '1']
                else:
                    student_doc['dropout'] = False
            else:
                gpa = student_doc.get('currentGPA', 3.0)
                attendance = ml_features_doc.get('attendance', 80.0)
                student_doc['dropout'] = (gpa is not None and gpa < 2.0) or (attendance is not None and attendance < 70.0)

            student_doc['last_updated'] = datetime.utcnow()

            try:
                result = students_col.update_one(
                    {'student_id': student_doc['student_id']},
                    {'$set': student_doc},
                    upsert=True
                )
                ingested_count += 1
            except Exception as e:
                logger.error(f"Failed to ingest student {student_doc.get('student_id')}: {e}", exc_info=True)
                self.update_state(state='PROGRESS', meta={'message': f'Failed to ingest {student_doc.get("student_id")}', 'error': str(e)})

        logger.info(f"Successfully ingested {ingested_count} records from '{file_path}' into MongoDB.")

        db.uploaded_datasets.insert_one({
            'dataset_name': model_name,
            'uploaded_by': ObjectId(user_id_str) if user_id_str else None,
            'uploaded_at': datetime.utcnow(),
            'original_file_name': os.path.basename(file_path),
            'is_paid': is_paid,
            'row_count': len(df_uploaded),
            'ingested_row_count': ingested_count,
            'status': 'ingested_and_training_triggered'
        })

        df_for_training = load_and_prepare_student_data()
        if df_for_training.empty:
            self.update_state(state='FAILURE', meta={'reason': 'No data for training'})
            return {'status': 'FAILURE', 'message': 'No data for training.'}

        training_result = train_dropout_models(df_for_training, dataset_name=model_name)

        db.uploaded_datasets.update_one(
            {'dataset_name': model_name, 'uploaded_by': ObjectId(user_id_str)},
            {'$set': {
                'status': 'training_complete',
                'training_metrics': training_result.get('metrics', {}),
                'trained_model_path': training_result.get('model_path', '')
            }}
        )

        logger.info(f"Model trained for dataset '{model_name}'.")
        return {'status': 'SUCCESS', 'message': f"Model '{model_name}' trained.", 'metrics': training_result.get('metrics')}

    except Exception as e:
        logger.error(f"Celery task failed for {model_name}: {e}", exc_info=True)
        self.update_state(state='FAILURE', meta={'reason': str(e)})
        return {'status': 'FAILURE', 'message': str(e)}

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Removed temp file: {file_path}")
