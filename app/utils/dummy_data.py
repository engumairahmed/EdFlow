# app/utils/dummy_data.py

from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId
import random

def create_dummy_data(db):
    """
    Creates dummy data for all necessary collections and users for each role
    if the 'users' collection is empty.
    """
    users_col = db.users
    students_col = db.students
    teachers_col = db.teachers
    courses_col = db.courses
    alerts_col = db.alerts
    feedbacks_col = db.feedbacks
    contacts_col = db.contacts
    lms_logs_col = db.lms_logs
    otp_codes_col = db.otp_codes

    if users_col.count_documents({}) > 0:
        print("Dummy data already exists. Skipping dummy data creation.")
        return

    print("Creating dummy data...")

    # --- 1. Create Users for Each Role ---
    hashed_password = generate_password_hash("password123", method='pbkdf2:sha256', salt_length=16)

    dummy_users_data = [
        {"username": "adminuser", "email": "admin@edflow.com", "role": "admin"},
        {"username": "analystuser", "email": "analyst@edflow.com", "role": "analyst"},
        {"username": "teacheruser", "email": "teacher@edflow.com", "role": "teacher"},
        {"username": "studentuser1", "email": "student1@edflow.com", "role": "student"},
        {"username": "studentuser2", "email": "student2@edflow.com", "role": "student"},
        {"username": "studentuser3", "email": "student3@edflow.com", "role": "student"},
        {"username": "studentuser4", "email": "student4@edflow.com", "role": "student"},
        {"username": "studentuser5", "email": "student5@edflow.com", "role": "student"},
    ]

    dummy_users = []
    for user_data in dummy_users_data:
        user_data["_id"] = ObjectId()
        user_data["password"] = hashed_password
        user_data["is_verified"] = True
        user_data["plan"] = "free"
        user_data["createdAt"] = datetime.now()
        user_data["lastLogin"] = datetime.now()
        dummy_users.append(user_data)
    
    users_col.insert_many(dummy_users)
    print("Dummy users created.")

    user_ids = {user["username"]: user["_id"] for user in dummy_users}

    admin_user_id = user_ids["adminuser"]
    analyst_user_id = user_ids["analystuser"]
    teacher_user_id = user_ids["teacheruser"]
    student_user_ids = [user_ids[f"studentuser{i}"] for i in range(1, 6)]

    # --- 2. Create Dummy Students ---
    # Incorporating features from the image and adding 'is_dropout'
    dummy_students = []
    
    student_data_configs = [
        # Student 1: Low risk
        {
            "userId": student_user_ids[0], "studentID": "S001", "dateOfBirth": datetime(2003, 5, 10),
            "gender": "Male", "ethnicity": "Asian", "socioeconomicStatus": "Middle",
            "highSchoolGPA": 3.8, "entranceExamScores": {"SAT": 1450}, "financialAidStatus": "Recipient",
            "currentGPA": 3.5,
            "study_hours": 15, "social_media_time": 2, "netflix_hours": 1, "part_time_job": "No",
            "attendance": 95, "sleep_hours": 8, "diet_quality": "Good", "exercise_frequency": "High",
            "parental_education_level": "Master", "internet_quality": "Good", "mental_health_score": 90,
            "extracurricular_activities": "Yes", "exam_score": 92
        },
        # Student 2: Medium risk (lower GPA, higher social/netflix, average attendance)
        {
            "userId": student_user_ids[1], "studentID": "S002", "dateOfBirth": datetime(2002, 8, 20),
            "gender": "Female", "ethnicity": "Caucasian", "socioeconomicStatus": "Middle",
            "highSchoolGPA": 3.2, "entranceExamScores": {"SAT": 1300}, "financialAidStatus": "None",
            "currentGPA": 2.8,
            "study_hours": 10, "social_media_time": 6, "netflix_hours": 4, "part_time_job": "No",
            "attendance": 85, "sleep_hours": 7, "diet_quality": "Average", "exercise_frequency": "Moderate",
            "parental_education_level": "Bachelor", "internet_quality": "Average", "mental_health_score": 70,
            "extracurricular_activities": "No", "exam_score": 75
        },
        # Student 3: High risk (low GPA, high time-wasters, low attendance) -> Labeled as dropout for training
        {
            "userId": student_user_ids[2], "studentID": "S003", "dateOfBirth": datetime(2004, 2, 1),
            "gender": "Male", "ethnicity": "Hispanic", "socioeconomicStatus": "Low",
            "highSchoolGPA": 2.5, "entranceExamScores": {"SAT": 1050}, "financialAidStatus": "Recipient",
            "currentGPA": 1.9, # Low GPA
            "study_hours": 5, "social_media_time": 10, "netflix_hours": 8, "part_time_job": "Yes",
            "attendance": 60, # Low attendance
            "sleep_hours": 6, "diet_quality": "Poor", "exercise_frequency": "Low",
            "parental_education_level": "High School", "internet_quality": "Poor", "mental_health_score": 45,
            "extracurricular_activities": "No", "exam_score": 55
        },
        # Student 4: Medium-High risk (struggling, but not dropout yet)
        {
            "userId": student_user_ids[3], "studentID": "S004", "dateOfBirth": datetime(2003, 11, 25),
            "gender": "Female", "ethnicity": "African American", "socioeconomicStatus": "Middle",
            "highSchoolGPA": 3.0, "entranceExamScores": {"ACT": 25}, "financialAidStatus": "None",
            "currentGPA": 2.2,
            "study_hours": 8, "social_media_time": 7, "netflix_hours": 5, "part_time_job": "Yes",
            "attendance": 75, "sleep_hours": 6.5, "diet_quality": "Average", "exercise_frequency": "Moderate",
            "parental_education_level": "Bachelor", "internet_quality": "Average", "mental_health_score": 60,
            "extracurricular_activities": "Yes", "exam_score": 68
        },
        # Student 5: Low risk (good overall)
        {
            "userId": student_user_ids[4], "studentID": "S005", "dateOfBirth": datetime(2005, 3, 15),
            "gender": "Female", "ethnicity": "Asian", "socioeconomicStatus": "High",
            "highSchoolGPA": 4.0, "entranceExamScores": {"SAT": 1550}, "financialAidStatus": "None",
            "currentGPA": 3.9,
            "study_hours": 20, "social_media_time": 1, "netflix_hours": 0.5, "part_time_job": "No",
            "attendance": 98, "sleep_hours": 8.5, "diet_quality": "Good", "exercise_frequency": "High",
            "parental_education_level": "PhD", "internet_quality": "Good", "mental_health_score": 95,
            "extracurricular_activities": "Yes", "exam_score": 95
        }
    ]

    for student_config in student_data_configs:
        student_doc = {
            "userId": student_config["userId"],
            "studentID": student_config["studentID"],
            "dateOfBirth": student_config["dateOfBirth"],
            "gender": student_config["gender"],
            "ethnicity": student_config["ethnicity"],
            "socioeconomicStatus": student_config["socioeconomicStatus"],
            "highSchoolGPA": student_config["highSchoolGPA"],
            "entranceExamScores": student_config["entranceExamScores"],
            "enrollmentHistory": [], # Will be populated later
            "lmsActivitySummary": {
                "lastLoginDate": datetime.now() - timedelta(days=random.randint(1, 30)),
                "totalLogins": random.randint(20, 100),
                "avgTimeOnLMSPerWeek": random.uniform(2, 15),
                "assignmentsSubmittedCount": random.randint(5, 20),
                "quizAverageScore": random.uniform(60, 95)
            },
            "financialAidStatus": student_config["financialAidStatus"],
            "currentGPA": student_config["currentGPA"],
            "riskFactors": [],
            "notes": [],
            # New fields from exemplary data
             "ml_features":{
                "study_hours": student_config["study_hours"],
                "social_media_time": student_config["social_media_time"],
                "netflix_hours": student_config["netflix_hours"],
                "part_time_job": student_config["part_time_job"],
                "attendance": student_config["attendance"],
                "sleep_hours": student_config["sleep_hours"],
                "diet_quality": student_config["diet_quality"],
                "exercise_frequency": student_config["exercise_frequency"],
                "parental_education_level": student_config["parental_education_level"],
                "internet_quality": student_config["internet_quality"],
                "mental_health_score": student_config["mental_health_score"],
                "extracurricular_activities": student_config["extracurricular_activities"],
                "exam_score": student_config["exam_score"],
             },
            # Define 'is_dropout' based on conditions
            "is_dropout": True if (student_config["currentGPA"] < 2.0 or student_config["attendance"] < 70) else False,
            "dropoutPredictionScore": None # Reset this, as we'll predict it
        }
        dummy_students.append(student_doc)

    students_col.insert_many(dummy_students)
    print("Dummy students created.")

    # Get the student IDs for enrollment history and LMS logs
    student_id_map = {s["studentID"]: s["userId"] for s in dummy_students}

    # --- 3. Create Dummy Teachers ---
    dummy_teachers = [
        {
            "userId": teacher_user_id,
            "teacherID": "T001",
            "department": "Computer Science",
            "coursesTaught": [],
            "qualifications": ["PhD in CS", "Certified Educator"],
            "officeHours": "Mon/Wed 10-12 PM"
        }
    ]
    teachers_col.insert_many(dummy_teachers)
    print("Dummy teachers created.")

    # --- 4. Create Dummy Courses ---
    dummy_courses = [
        {
            "courseCode": "CS101",
            "courseName": "Introduction to Programming",
            "description": "Foundational course in programming concepts.",
            "department": "Computer Science",
            "credits": 3,
            "prerequisites": [],
            "maxCapacity": 100,
            "currentEnrollment": 60,
            "instructorId": teacher_user_id,
            "syllabusURL": "http://example.com/cs101_syllabus.pdf",
            "historicalEnrollment": [
                {"semester": "Fall", "year": 2023, "enrollmentCount": 90},
                {"semester": "Spring", "year": 2024, "enrollmentCount": 85}
            ],
            "courseDemandPrediction": 0.8
        },
        {
            "courseCode": "MA201",
            "courseName": "Calculus I",
            "description": "First course in differential calculus.",
            "department": "Mathematics",
            "credits": 4,
            "prerequisites": [],
            "maxCapacity": 80,
            "currentEnrollment": 75,
            "instructorId": None,
            "syllabusURL": "http://example.com/ma201_syllabus.pdf",
            "historicalEnrollment": [
                {"semester": "Fall", "year": 2023, "enrollmentCount": 70},
                {"semester": "Spring", "year": 2024, "enrollmentCount": 78}
            ],
            "courseDemandPrediction": 0.7
        }
    ]
    courses_col.insert_many(dummy_courses)
    print("Dummy courses created.")

    cs101_course_id = courses_col.find_one({"courseCode": "CS101"})["_id"]
    ma201_course_id = courses_col.find_one({"courseCode": "MA201"})["_id"]

    # --- Populate Enrollment History and LMS Logs for multiple students ---
    # Enroll all students in CS101 and MA201 for consistency
    for s_id in student_id_map.values():
        students_col.update_one(
            {"userId": s_id},
            {"$push": {"enrollmentHistory": {
                "courseId": cs101_course_id,
                "semester": "Fall",
                "year": 2024,
                "grade": random.choice(["A", "B+", "B", "C+", "C", "D", "F"]),
                "creditsEarned": 3,
                "enrollmentDate": datetime.now() - timedelta(days=random.randint(60, 90)),
                "status": "completed",
                "attendanceRecords": [
                    {"date": datetime.now() - timedelta(days=d), "status": random.choice(["Present", "Absent", "Tardy"])}
                    for d in random.sample(range(1, 60), 10) # 10 random attendance records
                ]
            }}}
        )
        students_col.update_one(
            {"userId": s_id},
            {"$push": {"enrollmentHistory": {
                "courseId": ma201_course_id,
                "semester": "Fall",
                "year": 2024,
                "grade": random.choice(["A", "B+", "B", "C+", "C", "D", "F"]),
                "creditsEarned": 4,
                "enrollmentDate": datetime.now() - timedelta(days=random.randint(60, 90)),
                "status": "in_progress", # Some current course
                "attendanceRecords": [
                    {"date": datetime.now() - timedelta(days=d), "status": random.choice(["Present", "Absent", "Tardy"])}
                    for d in random.sample(range(1, 60), 10) # 10 random attendance records
                ]
            }}}
        )

        # Create some LMS logs for each student
        for _ in range(random.randint(5, 20)): # 5 to 20 random logs per student
            lms_logs_col.insert_one({
                "studentId": s_id,
                "courseId": random.choice([cs101_course_id, ma201_course_id]),
                "activityType": random.choice(["page_view", "quiz_attempt", "assignment_view", "discussion_post", "video_watched"]),
                "timestamp": datetime.now() - timedelta(hours=random.randint(1, 720)), # Up to 30 days ago
                "details": {"score": random.uniform(50, 100)} if random.random() > 0.7 else {}
            })


    teachers_col.update_one(
        {"userId": teacher_user_id},
        {"$push": {"coursesTaught": {
            "courseId": cs101_course_id,
            "semester": "Fall",
            "year": 2024
        }}}
    )

    # --- 5. Create Dummy Alerts ---
    dummy_alerts = [
        {
            "alertType": "dropout_risk",
            "targetEntityId": student_id_map["S003"], # S003 is our dropout example
            "targetEntityType": "student",
            "message": "Student S003 shows high risk of dropout due to low engagement and grades.",
            "severity": "high",
            "generatedAt": datetime.now() - timedelta(days=5),
            "status": "new",
            "acknowledgedBy": None,
            "acknowledgedAt": None
        },
        {
            "alertType": "low_performance",
            "targetEntityId": student_id_map["S002"],
            "targetEntityType": "student",
            "message": "Student S002 has a failing grade in MA201.",
            "severity": "medium",
            "generatedAt": datetime.now() - timedelta(days=2),
            "status": "new",
            "acknowledgedBy": None,
            "acknowledgedAt": None
        }
    ]
    alerts_col.insert_many(dummy_alerts)
    print("Dummy alerts created.")

    # --- 6. Create Dummy Feedbacks ---
    dummy_feedbacks = [
        {
            "userId": student_id_map["S001"],
            "subject": "LMS Usability",
            "message": "The LMS interface is sometimes slow and confusing.",
            "rating": 3,
            "verified": True,
            "createdAt": datetime.now() - timedelta(days=10)
        },
        {
            "userId": teacher_user_id,
            "subject": "Course Content Suggestion",
            "message": "Consider adding more practical examples in CS101.",
            "rating": 4,
            "verified": True,
            "createdAt": datetime.now() - timedelta(days=7)
        }
    ]
    feedbacks_col.insert_many(dummy_feedbacks)
    print("Dummy feedbacks created.")

    # --- 7. Create Dummy Contacts ---
    dummy_contacts = [
        {
            "name": "Jane Public",
            "email": "jane.public@example.com",
            "subject": "General Inquiry",
            "message": "I have a question about the EdFlow platform.",
            "createdAt": datetime.now() - timedelta(days=15)
        }
    ]
    contacts_col.insert_many(dummy_contacts)
    print("Dummy contacts created.")

    # OTP codes are not created in bulk for dummy data as they are transient

    print("Dummy data creation complete.")