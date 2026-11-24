from desktop.companion.phone_discovery import _phone_id


def test_phone_advertisement_checks_version_and_identifier():
    identity = b"ab" * 16

    def txt(*fields):
        return b"".join(bytes((len(field),)) + field for field in fields)

    assert _phone_id(txt(b"v=1", b"id=" + identity)) == identity.decode()
    assert _phone_id(txt(b"v=2", b"id=" + identity)) is None
    assert _phone_id(txt(b"v=1", b"id=" + identity, b"id=" + identity)) is None
    assert _phone_id(txt(b"v=1", b"id=short")) is None
    assert _phone_id(txt(b"v=1", b"id=" + identity)[:-1]) is None
