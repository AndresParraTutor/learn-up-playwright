from __future__ import annotations

import yaml
from yaml.events import AliasEvent, NodeEvent

from .types import Manifest, TopicTransferError


def dump_manifest(manifest: Manifest) -> bytes:
    manifest.validate()
    text = yaml.safe_dump(
        manifest.as_mapping(),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=1000,
    )
    return text.replace("\r\n", "\n").encode("utf-8")


def load_manifest(data: bytes) -> Manifest:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TopicTransferError("manifest.yaml is not valid UTF-8") from exc
    if "\x00" in text:
        raise TopicTransferError("manifest.yaml contains a NUL byte")
    try:
        for event in yaml.parse(text):
            if isinstance(event, AliasEvent):
                raise TopicTransferError("manifest.yaml cannot contain YAML aliases")
            if isinstance(event, NodeEvent) and event.anchor is not None:
                raise TopicTransferError("manifest.yaml cannot contain YAML anchors")
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TopicTransferError("manifest.yaml is malformed") from exc
    return Manifest.from_mapping(value)
