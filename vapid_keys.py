import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip("=")

def generate_vapid_keys():
    # Generate EC private key using the SECP256R1 curve
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Export private key in PEM format (optional, for backend)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Export private key in raw bytes (for encoding to base64)
    private_raw = private_key.private_numbers().private_value.to_bytes(32, byteorder='big')
    private_b64 = base64url_encode(private_raw)

    # Get public key and encode to uncompressed point format (04 + X + Y)
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()
    x = public_numbers.x.to_bytes(32, byteorder='big')
    y = public_numbers.y.to_bytes(32, byteorder='big')
    public_key_bytes = b'\x04' + x + y
    public_b64 = base64url_encode(public_key_bytes)

    print("🔐 Private VAPID Key (Base64, for Flask backend):")
    print(private_b64)

    print("\n🔑 Public VAPID Key (Base64, for JS frontend):")
    print(public_b64)

if __name__ == "__main__":
    generate_vapid_keys()
