from pyatrea.transport import AtreaTransport, Descriptors


def test_descriptors_defaults_empty():
    d = Descriptors()
    assert d.config_dir is None
    assert d.translations == {"params": {}, "words": {}}
    assert d.user_labels == {}
    assert d.ids_to_modes == {} and d.modes_to_ids == {} and d.forced_modes == {}


def test_transport_protocol_surface():
    for m in ("connect", "read", "write", "read_descriptors", "is_atrea_unit", "close"):
        assert hasattr(AtreaTransport, m)
