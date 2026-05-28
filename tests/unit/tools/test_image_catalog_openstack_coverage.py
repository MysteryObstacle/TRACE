from trace.tools.images.loader import OPENSTACK_OBTAIN_IMAGE_IDS, find_images, load_catalog_model, openstack_guide_image_ids


def test_openstack_obtain_images_ids_exist_in_registry() -> None:
    registry_ids = set(openstack_guide_image_ids())
    missing = [image_id for image_id in OPENSTACK_OBTAIN_IMAGE_IDS if image_id not in registry_ids]
    assert not missing, f"missing openstack guide images: {missing}"


def test_openstack_guide_has_full_obtain_images_coverage() -> None:
    assert len(openstack_guide_image_ids()) == len(OPENSTACK_OBTAIN_IMAGE_IDS)
    assert len(openstack_guide_image_ids()) >= 23


def test_find_images_can_discover_each_openstack_family() -> None:
    probes = {
        "almalinux_9": ("almalinux", None),
        "ubuntu_24": ("ubuntu 24", None),
        "cirros": ("cirros", None),
        "windows_server_2022": ("windows server", None),
        "freebsd": ("freebsd", None),
    }
    for image_id, (query, roles) in probes.items():
        matches = find_images(query=query, roles=roles, node_type="computer", limit=5)
        match_ids = {item["id"] for item in matches}
        assert image_id in match_ids, f"find_images did not surface {image_id} for query={query!r}"


def test_catalog_json_has_unique_ids() -> None:
    ids = [item.id for item in load_catalog_model().images]
    assert len(ids) == len(set(ids))
