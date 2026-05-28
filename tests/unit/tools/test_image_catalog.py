from trace.tools.images.catalog import find_images, get_image, image_catalog_prompt


def test_image_catalog_resolves_firewall_and_internet_gateway_images():
    firewall = get_image("pfsense")
    internet = get_image("linux_internet_gateway")

    assert firewall["image"] == {"id": "pfsense", "name": "pfSense Community Edition"}
    assert firewall["default_flavor"] == {"vcpu": 2, "ram": 2048, "disk": 10}
    assert "firewall" in firewall["roles"]
    assert internet["image"] == {"id": "linux_internet_gateway", "name": "Linux Internet Gateway"}
    assert "internet_gateway" in internet["roles"]


def test_image_catalog_can_query_by_role_alias_and_node_type():
    firewall_matches = find_images(query="firewall appliance", roles=["firewall"], node_type="computer")
    internet_matches = find_images(query="simulated internet", roles=["internet_gateway"], node_type="computer")

    assert firewall_matches[0]["id"] == "pfsense"
    assert internet_matches[0]["id"] == "linux_internet_gateway"


def test_image_catalog_covers_open_ics_role_capabilities():
    scada_matches = find_images(query="SCADA capability", roles=["scada"], node_type="computer")
    hmi_matches = find_images(query="HMI capability", roles=["hmi"], node_type="computer")
    historian_matches = find_images(
        query="industrial historian capability",
        roles=["industrial_historian"],
        node_type="computer",
    )
    engineering_matches = find_images(
        query="engineering workstation capability",
        roles=["engineering_workstation"],
        node_type="computer",
    )

    assert scada_matches[0]["id"] == "scada_workstation"
    assert hmi_matches[0]["id"] == "hmi_workstation"
    assert historian_matches[0]["id"] == "industrial_historian"
    assert engineering_matches[0]["id"] == "engineering_workstation"


def test_image_catalog_prompt_exposes_exact_ids_for_llm_stages():
    prompt = image_catalog_prompt()

    assert "pfsense" in prompt
    assert "linux_internet_gateway" in prompt
    assert "scada_workstation" in prompt
    assert "hmi_workstation" in prompt
    assert "industrial_historian" in prompt
    assert "engineering_workstation" in prompt
    assert "Use these exact image.id values" in prompt


def test_legacy_ids_still_resolve_via_get_image():
    assert get_image("img-fw")["id"] == "pfsense"
