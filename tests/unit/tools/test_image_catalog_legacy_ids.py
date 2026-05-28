import pytest

from trace.tools.images.loader import get_image, resolve_image_id


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("img_ubuntu_22", "ubuntu_22"),
        ("img-ubuntu-22", "ubuntu_22"),
        ("img-fw", "pfsense"),
        ("img_pfsense", "pfsense"),
        ("img-inet", "linux_internet_gateway"),
        ("img-tiny-linux", "tiny_linux"),
    ],
)
def test_resolve_image_id_maps_legacy_values(legacy: str, canonical: str) -> None:
    assert resolve_image_id(legacy) == canonical
    record = get_image(legacy)
    assert record["id"] == canonical


def test_resolve_image_id_rejects_unknown() -> None:
    with pytest.raises(KeyError, match="unknown image id"):
        resolve_image_id("not-a-real-image")
