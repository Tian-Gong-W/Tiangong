from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .model import KnowledgeKind, KnowledgeRecord, parse_datetime, utcnow

_USER_AGENT = "TONMEN-KnowledgeCrawler/0.1 (+https://github.com/Top-Men-AI/Tiangong)"
_CISA_KEV_MIRROR = (
    "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"
)
_NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def stable_record_id(source: str, external_id: str) -> str:
    material = f"{source.strip().casefold()}\0{external_id.strip().casefold()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


def _public_https_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("knowledge sources must use public HTTPS URLs")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost":
        raise ValueError("localhost knowledge sources are not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise ValueError("private or non-global knowledge source addresses are not allowed")
    return parsed.geturl()


def _resolved_public(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return True
    for item in addresses:
        address = item[4][0]
        try:
            if not ipaddress.ip_address(address).is_global:
                return False
        except ValueError:
            return False
    return True


def fetch_bytes(url: str, *, timeout: int = 30, max_bytes: int = 8_000_000) -> bytes:
    validated = _public_https_url(url)
    host = urlparse(validated).hostname or ""
    if not _resolved_public(host):
        raise ValueError("knowledge source resolved to a non-public address")
    request = Request(
        validated,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/json, application/atom+xml, application/rss+xml, text/xml, text/plain;q=0.8",
        },
    )
    with urlopen(request, timeout=max(1, int(timeout))) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("knowledge source response exceeds configured size limit")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("knowledge source response exceeds configured size limit")
    return data


def fetch_json(url: str, *, timeout: int = 30, max_bytes: int = 8_000_000) -> Mapping[str, Any]:
    data = json.loads(fetch_bytes(url, timeout=timeout, max_bytes=max_bytes).decode("utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("knowledge JSON source must return an object")
    return data


def _text(value: Any) -> str:
    return " ".join(unescape(str(value or "")).split())


def _date(value: Any, *, default: datetime | None = None) -> datetime:
    text = str(value or "").strip()
    if not text:
        return default or utcnow()
    try:
        return parse_datetime(text)
    except (TypeError, ValueError):
        try:
            resolved = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return default or utcnow()
        if resolved.tzinfo is None:
            resolved = resolved.replace(tzinfo=timezone.utc)
        return resolved.astimezone(timezone.utc)


def cisa_kev_records(*, url: str = _CISA_KEV_MIRROR, now: datetime | None = None) -> tuple[KnowledgeRecord, ...]:
    current = now or utcnow()
    payload = fetch_json(url, max_bytes=12_000_000)
    items = payload.get("vulnerabilities")
    if not isinstance(items, list):
        return ()
    records: list[KnowledgeRecord] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        cve = str(item.get("cveID") or "").strip().upper()
        vendor = _text(item.get("vendorProject"))
        product = _text(item.get("product"))
        if not cve:
            continue
        ransomware = _text(item.get("knownRansomwareCampaignUse"))
        cwes = item.get("cwes") if isinstance(item.get("cwes"), list) else []
        tags = ["general", "cisa-kev", "known-exploited", cve]
        tags.extend(str(cwe) for cwe in cwes if str(cwe).strip())
        if ransomware and ransomware.casefold() not in {"unknown", "none"}:
            tags.append("ransomware-observed")
        records.append(
            KnowledgeRecord.create(
                record_id=stable_record_id("cisa-kev", cve),
                kind=KnowledgeKind.THREAT_PATTERN,
                title=_text(item.get("vulnerabilityName")) or f"{cve} known exploited vulnerability",
                summary=_text(item.get("shortDescription")),
                source="CISA KEV",
                source_url=url,
                published_at=_date(item.get("dateAdded"), default=current),
                retrieved_at=current,
                confidence=0.98,
                source_trust=1.0,
                max_age_days=365,
                technologies=[vendor, product, f"{vendor} {product}".strip()],
                tags=tags,
                required_products=("validation_observation",),
                preferred_modalities=("http", "network"),
                metadata={
                    "external_id": cve,
                    "vendor": vendor,
                    "product": product,
                    "due_date": item.get("dueDate"),
                    "required_action": _text(item.get("requiredAction")),
                    "known_ransomware_campaign_use": ransomware or None,
                    "source_family": "cisa-kev",
                },
            )
        )
    return tuple(records)


def _cpe_products(node: Any) -> tuple[tuple[str, str], ...]:
    products: list[tuple[str, str]] = []

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            criteria = value.get("criteria")
            if isinstance(criteria, str) and criteria.startswith("cpe:2.3:"):
                parts = criteria.split(":")
                if len(parts) > 4:
                    vendor = parts[3].replace("_", " ").strip()
                    product = parts[4].replace("_", " ").strip()
                    pair = (vendor, product)
                    if pair not in products:
                        products.append(pair)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return tuple(products)


def _nvd_severity(cve: Mapping[str, Any]) -> str:
    metrics = cve.get("metrics") if isinstance(cve.get("metrics"), Mapping) else {}
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        values = metrics.get(key)
        if not isinstance(values, list):
            continue
        for metric in values:
            if not isinstance(metric, Mapping):
                continue
            data = metric.get("cvssData") if isinstance(metric.get("cvssData"), Mapping) else {}
            severity = str(data.get("baseSeverity") or metric.get("baseSeverity") or "").strip().lower()
            if severity:
                return severity
    return "unknown"


def _english_description(cve: Mapping[str, Any]) -> str:
    descriptions = cve.get("descriptions")
    if not isinstance(descriptions, list):
        return ""
    for item in descriptions:
        if isinstance(item, Mapping) and str(item.get("lang") or "").lower() == "en":
            return _text(item.get("value"))
    for item in descriptions:
        if isinstance(item, Mapping):
            return _text(item.get("value"))
    return ""


def nvd_recent_records(
    *,
    now: datetime | None = None,
    lookback_hours: int = 36,
    max_pages: int = 3,
) -> tuple[KnowledgeRecord, ...]:
    current = (now or utcnow()).astimezone(timezone.utc)
    start = current - timedelta(hours=max(1, min(240, int(lookback_hours))))
    params = {
        "pubStartDate": start.isoformat(timespec="milliseconds"),
        "pubEndDate": current.isoformat(timespec="milliseconds"),
        "resultsPerPage": "2000",
    }
    index = 0
    pages = 0
    records: list[KnowledgeRecord] = []
    while pages < max(1, int(max_pages)):
        query = dict(params)
        query["startIndex"] = str(index)
        payload = fetch_json(f"{_NVD_CVE_API}?{urlencode(query)}", max_bytes=14_000_000)
        vulnerabilities = payload.get("vulnerabilities")
        if not isinstance(vulnerabilities, list):
            break
        for wrapper in vulnerabilities:
            if not isinstance(wrapper, Mapping):
                continue
            cve = wrapper.get("cve") if isinstance(wrapper.get("cve"), Mapping) else {}
            cve_id = str(cve.get("id") or "").strip().upper()
            if not cve_id:
                continue
            products = _cpe_products(cve.get("configurations"))
            technology_terms = [term for vendor, product in products for term in (vendor, product, f"{vendor} {product}")]
            severity = _nvd_severity(cve)
            weaknesses = cve.get("weaknesses") if isinstance(cve.get("weaknesses"), list) else []
            cwe_tags: list[str] = []
            for weakness in weaknesses:
                descriptions = weakness.get("description") if isinstance(weakness, Mapping) else None
                if not isinstance(descriptions, list):
                    continue
                for description in descriptions:
                    if isinstance(description, Mapping):
                        value = str(description.get("value") or "").strip()
                        if value.startswith("CWE-") and value not in cwe_tags:
                            cwe_tags.append(value)
            records.append(
                KnowledgeRecord.create(
                    record_id=stable_record_id("nvd", cve_id),
                    kind=KnowledgeKind.THREAT_PATTERN,
                    title=f"{cve_id} published vulnerability",
                    summary=_english_description(cve),
                    source="NVD",
                    source_url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    published_at=_date(cve.get("published"), default=current),
                    retrieved_at=current,
                    confidence=0.92,
                    source_trust=0.98,
                    max_age_days=120,
                    technologies=technology_terms,
                    tags=("nvd", "cve", cve_id, f"severity:{severity}", *cwe_tags),
                    required_products=("validation_observation",),
                    metadata={
                        "external_id": cve_id,
                        "severity": severity,
                        "vendor_products": [list(item) for item in products],
                        "source_family": "nvd",
                    },
                )
            )
        total = int(payload.get("totalResults") or 0)
        per_page = int(payload.get("resultsPerPage") or len(vulnerabilities) or 1)
        index += per_page
        pages += 1
        if not vulnerabilities or index >= total:
            break
    return tuple(records)


@dataclass(frozen=True, slots=True)
class FeedSpec:
    name: str
    url: str
    kind: KnowledgeKind = KnowledgeKind.PRODUCT_CHANGE
    source_trust: float = 0.9
    max_age_days: int = 90
    entity: str | None = None
    product_category: str | None = None
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FeedSpec":
        kind_value = str(data.get("kind") or KnowledgeKind.PRODUCT_CHANGE.value)
        return cls(
            name=str(data.get("name") or data.get("url") or "feed").strip(),
            url=_public_https_url(str(data.get("url") or "")),
            kind=KnowledgeKind(kind_value),
            source_trust=max(0.0, min(1.0, float(data.get("source_trust", 0.9)))),
            max_age_days=max(1, int(data.get("max_age_days", 90))),
            entity=str(data.get("entity") or "").strip() or None,
            product_category=str(data.get("product_category") or "").strip() or None,
            tags=tuple(str(item).strip() for item in data.get("tags", ()) if str(item).strip()),
        )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, names: Iterable[str]) -> str:
    wanted = {name.lower() for name in names}
    for child in node.iter():
        if _local_name(child.tag) in wanted and child.text and child.text.strip():
            return _text(child.text)
    return ""


def _entry_link(node: ET.Element) -> str:
    for child in node.iter():
        if _local_name(child.tag) != "link":
            continue
        href = str(child.attrib.get("href") or "").strip()
        if href:
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def rss_atom_records(spec: FeedSpec, *, now: datetime | None = None) -> tuple[KnowledgeRecord, ...]:
    current = now or utcnow()
    root = ET.fromstring(fetch_bytes(spec.url, max_bytes=5_000_000))
    entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    records: list[KnowledgeRecord] = []
    for entry in entries[:500]:
        title = _child_text(entry, ("title",))
        link = _entry_link(entry)
        external_id = _child_text(entry, ("id", "guid")) or link or title
        if not external_id:
            continue
        summary = _child_text(entry, ("summary", "description", "content"))
        published = _child_text(entry, ("published", "updated", "pubdate", "date"))
        tags = ["feed", *spec.tags]
        technologies = []
        if spec.entity:
            tags.append(f"entity:{spec.entity}")
            technologies.append(spec.entity)
        if spec.product_category:
            tags.append(f"product:{spec.product_category}")
        records.append(
            KnowledgeRecord.create(
                record_id=stable_record_id(spec.name, external_id),
                kind=spec.kind,
                title=title or external_id,
                summary=summary,
                source=spec.name,
                source_url=link or spec.url,
                published_at=_date(published, default=current),
                retrieved_at=current,
                confidence=0.82,
                source_trust=spec.source_trust,
                max_age_days=spec.max_age_days,
                technologies=technologies,
                tags=tags,
                metadata={
                    "external_id": external_id,
                    "entity": spec.entity,
                    "product_category": spec.product_category,
                    "feed_url": spec.url,
                    "source_family": "rss-atom",
                },
            )
        )
    return tuple(records)
