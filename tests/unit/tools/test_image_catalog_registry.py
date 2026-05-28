from trace.tools.images.loader import ImageCatalogModel, catalog_json_path, load_catalog_model


def test_catalog_json_loads_with_pydantic() -> None:
    model = load_catalog_model()
    assert model.schema_version == 1
    assert len(model.images) >= 30


def test_catalog_file_path_points_at_repo_data() -> None:
    path = catalog_json_path()
    assert path.name == "image_catalog.v1.json"
    assert path.is_file()


def test_image_ids_do_not_use_img_prefix() -> None:
    model = load_catalog_model()
    for item in model.images:
        assert not item.id.startswith("img_"), item.id


def test_revalidate_from_raw_json_matches_cached_model() -> None:
    raw = catalog_json_path().read_text(encoding="utf-8")
    import json

    payload = json.loads(raw)
    reparsed = ImageCatalogModel.model_validate(payload)
    assert len(reparsed.images) == len(load_catalog_model().images)
