"""Persist P-256 signing keys in the default macOS Keychain."""
from __future__ import annotations

import re

import Security

from app.release import BUNDLE_IDENTIFIER


def keychain_tag(label: str) -> bytes:
    if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", label):
        raise ValueError("Use 1–64 letters, digits, hyphens or underscores for the Keychain tag.")
    return f"{BUNDLE_IDENTIFIER}.c2pa.{label}".encode("ascii")


class KeychainSigningKey:
    def __init__(self, key):
        attributes = Security.SecKeyCopyAttributes(key)
        if (attributes.get(Security.kSecAttrIsExtractable, True)
                or attributes.get(Security.kSecAttrKeySizeInBits) != 256
                or not Security.SecKeyIsAlgorithmSupported(
                    key, Security.kSecKeyOperationTypeSign,
                    Security.kSecKeyAlgorithmECDSASignatureMessageX962SHA256,
                )):
            raise ValueError("The Keychain key must be non-extractable and support P-256 signing.")
        self._key = key

    def public_key_bytes(self) -> bytes:
        public_key = Security.SecKeyCopyPublicKey(self._key)
        if public_key is None:
            raise OSError("The Keychain could not read the C2PA public key.")
        data, _ = Security.SecKeyCopyExternalRepresentation(public_key, None)
        if data is None:
            raise OSError("The Keychain could not export the C2PA public key.")
        return bytes(data)

    def sign(self, message: bytes) -> bytes:
        signature, _ = Security.SecKeyCreateSignature(
            self._key, Security.kSecKeyAlgorithmECDSASignatureMessageX962SHA256, message, None,
        )
        if signature is None:
            raise OSError("The Keychain could not sign with the C2PA key.")
        return bytes(signature)


def signing_key(label: str, *, create: bool = False) -> KeychainSigningKey:
    tag = keychain_tag(label)
    status, keychain = Security.SecKeychainCopyDefault(None)
    if status != Security.errSecSuccess:
        raise OSError(f"The default macOS Keychain is unavailable ({status}).")

    status, matches = Security.SecItemCopyMatching({
        Security.kSecClass: Security.kSecClassKey,
        Security.kSecAttrKeyClass: Security.kSecAttrKeyClassPrivate,
        Security.kSecAttrApplicationTag: tag,
        Security.kSecMatchSearchList: [keychain],
        Security.kSecMatchLimit: Security.kSecMatchLimitAll,
        Security.kSecReturnRef: True,
    }, None)
    if status == Security.errSecSuccess:
        if len(matches) != 1:
            raise ValueError("More than one Keychain key uses this C2PA tag. Choose a new tag.")
        return KeychainSigningKey(matches[0])
    if status != Security.errSecItemNotFound or not create:
        raise OSError(f"The configured C2PA key is unavailable in this Keychain ({status}).")

    status, app = Security.SecTrustedApplicationCreateFromPath(None, None)
    if status != Security.errSecSuccess:
        raise OSError(f"The Keychain could not identify the signing application ({status}).")
    description = f"AudioEnhancerMAX C2PA · {label}"
    status, access = Security.SecAccessCreate(description, [app], None)
    if status != Security.errSecSuccess:
        raise OSError(f"The Keychain could not restrict access to the signing key ({status}).")
    key, error = Security.SecKeyCreateRandomKey({
        Security.kSecUseKeychain: keychain,
        Security.kSecAttrKeyType: Security.kSecAttrKeyTypeECSECPrimeRandom,
        Security.kSecAttrKeySizeInBits: 256,
        Security.kSecAttrIsSensitive: True,
        Security.kSecAttrIsExtractable: False,
        Security.kSecAttrAccess: access,
        Security.kSecPrivateKeyAttrs: {
            Security.kSecAttrIsPermanent: True,
            Security.kSecAttrApplicationTag: tag,
            Security.kSecAttrLabel: description,
        },
    }, None)
    if key is None:
        raise OSError(f"The Keychain could not create the C2PA signing key ({error}).")
    return KeychainSigningKey(key)


def certificate_request(key: KeychainSigningKey, subject) -> bytes:
    """Return a PKCS#10 CSR signed by the Keychain key itself."""
    from asn1crypto import csr, pem, x509 as asn1_x509
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), key.public_key_bytes())
    public_der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    info = csr.CertificationRequestInfo({
        "version": "v1",
        "subject": asn1_x509.Name.load(subject.public_bytes()),
        "subject_pk_info": asn1_x509.PublicKeyInfo.load(public_der),
        "attributes": [],
    })
    request = csr.CertificationRequest({
        "certification_request_info": info,
        "signature_algorithm": {"algorithm": "sha256_ecdsa"},
        "signature": key.sign(info.dump()),
    })
    der = request.dump()
    if not x509.load_der_x509_csr(der).is_signature_valid:
        raise ValueError("The C2PA certificate request signature could not be verified.")
    return pem.armor("CERTIFICATE REQUEST", der)
