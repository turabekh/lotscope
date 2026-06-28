import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid01


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    vapid = Vapid01()
    vapid.generate_keys()
    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    public_point = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    print("VAPID_PRIVATE_KEY=" + _b64(private_raw))
    print("VAPID_PUBLIC_KEY=" + _b64(public_point))


if __name__ == "__main__":
    main()
