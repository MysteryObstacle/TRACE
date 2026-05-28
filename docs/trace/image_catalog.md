# TRACE Image Capability Registry

## Purpose

The image catalog is a **provider-neutral capability directory** for TRACE physical-stage deployment metadata. It is **not** a Glance image store: entries do not point to downloadable qcow2 artifacts.

## Files

| Path | Role |
|------|------|
| `data/trace/image_catalog.v1.json` | Canonical registry data |
| `data/trace/schemas/image_catalog.v1.schema.json` | JSON Schema for the registry file |
| `src/trace/tools/images/loader.py` | Load, resolve legacy ids, search |

## Image IDs

- Format: lowercase `snake_case` (e.g. `ubuntu_22`, `pfsense`).
- Do **not** use an `img_` prefix; the catalog already implies images.
- Legacy ids (`img_ubuntu_22`, `img-ubuntu-22`, `img-fw`, …) resolve via `resolve_image_id()`.

## Catalog groups

| `catalog_group` | Meaning |
|-----------------|--------|
| `openstack_image_guide` | Aligns with [OpenStack obtain-images](https://docs.openstack.org/image-guide/obtain-images.html) |
| `trace_lab` | Lab-only appliances (firewall sim, Internet node, ICS, PLC) |
| `network_device` | Router/switch templates; physical stage keeps `image` null on those nodes |

## OpenStack coverage

`OPENSTACK_OBTAIN_IMAGE_IDS` in `loader.py` lists the required obtain-images families (24 ids). CI asserts each id exists in the registry.

## Graph metadata shape

```json
{"id": "ubuntu_22", "name": "Ubuntu 22.04 LTS Cloud"}
```

Validators and checkpoints should compare canonical ids (after `resolve_image_id` when ingesting legacy demos).
