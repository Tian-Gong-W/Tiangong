from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping
from urllib.parse import urlparse

from tonmen.missions import MissionRun


class SurfaceScale(str, Enum):
    UNKNOWN = "unknown"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class OrganizationScale(str, Enum):
    UNKNOWN = "unknown"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class SecurityMaturity(str, Enum):
    UNKNOWN = "unknown"
    BASIC = "basic"
    MODERATE = "moderate"
    MATURE = "mature"


def _enum_hint(enum_type, value):
    text = str(value or "").strip().lower()
    try:
        return enum_type(text)
    except ValueError:
        return enum_type.UNKNOWN


def _unique(values) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class TargetProfile:
    """Evidence-derived target profile.

    Organization scale, industry and maturity remain UNKNOWN unless supplied by an
    explicit profile signal. Surface size is inferred only from observed assets and
    must not be confused with company size.
    """

    target: str
    technologies: tuple[str, ...]
    industries: tuple[str, ...]
    product_categories: tuple[str, ...]
    organization_scale: OrganizationScale
    security_maturity: SecurityMaturity
    surface_scale: SurfaceScale
    domain_count: int
    service_count: int
    web_origin_count: int
    endpoint_count: int
    profile_confidence: float = 0.0

    @classmethod
    def from_run(
        cls,
        run: MissionRun,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "TargetProfile":
        metadata = dict(metadata or {})
        technologies: list[str] = []
        industries: list[str] = []
        product_categories: list[str] = []
        domains: set[str] = set()
        services: set[tuple[str, str]] = set()
        web_origins: set[str] = set()
        endpoints: set[str] = set()

        explicit_profile: dict[str, Any] = {}
        for node in run.graph.nodes.values():
            if node.kind == "target.profile":
                node_meta = dict(node.metadata)
                confidence = float(node_meta.get("confidence") or 0.0)
                if confidence >= float(explicit_profile.get("confidence") or -1.0):
                    explicit_profile = node_meta
                continue
            if not node.kind.startswith("intelligence."):
                continue
            node_meta = dict(node.metadata)
            data = node_meta.get("data") if isinstance(node_meta.get("data"), dict) else {}
            kind = node.kind.removeprefix("intelligence.")
            if kind == "domain":
                host = str(data.get("host") or node_meta.get("target") or "").strip().lower()
                if host:
                    domains.add(host)
            elif kind == "service":
                host = str(node_meta.get("target") or data.get("scanned_address") or "").strip().lower()
                service = f"{data.get('port')}/{data.get('service')}"
                services.add((host, service))
            elif kind == "web":
                url = str(data.get("url") or node_meta.get("target") or "").strip()
                if url:
                    parsed = urlparse(url)
                    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else url
                    web_origins.add(origin)
                technologies.extend(data.get("technologies") or ())
            elif kind == "endpoint":
                url = str(data.get("url") or node_meta.get("target") or "").strip()
                if url:
                    endpoints.add(url)

        merged = {**metadata, **explicit_profile}
        technologies.extend(merged.get("technologies") or ())
        industries.extend(merged.get("industries") or ())
        product_categories.extend(merged.get("product_categories") or ())
        if merged.get("industry"):
            industries.append(str(merged["industry"]))
        if merged.get("product_category"):
            product_categories.append(str(merged["product_category"]))

        observed_units = len(domains) + len(services) + len(web_origins) + len(endpoints)
        if observed_units == 0:
            surface_scale = SurfaceScale.UNKNOWN
        elif observed_units <= 5:
            surface_scale = SurfaceScale.SMALL
        elif observed_units <= 25:
            surface_scale = SurfaceScale.MEDIUM
        else:
            surface_scale = SurfaceScale.LARGE

        confidence = float(merged.get("confidence") or 0.0)
        if technologies and confidence <= 0.0:
            confidence = 0.6

        return cls(
            target=run.target,
            technologies=_unique(technologies),
            industries=_unique(industries),
            product_categories=_unique(product_categories),
            organization_scale=_enum_hint(
                OrganizationScale,
                merged.get("organization_scale") or merged.get("company_size"),
            ),
            security_maturity=_enum_hint(
                SecurityMaturity,
                merged.get("security_maturity"),
            ),
            surface_scale=surface_scale,
            domain_count=len(domains),
            service_count=len(services),
            web_origin_count=len(web_origins),
            endpoint_count=len(endpoints),
            profile_confidence=max(0.0, min(1.0, confidence)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "technologies": list(self.technologies),
            "industries": list(self.industries),
            "product_categories": list(self.product_categories),
            "organization_scale": self.organization_scale.value,
            "security_maturity": self.security_maturity.value,
            "surface_scale": self.surface_scale.value,
            "domain_count": self.domain_count,
            "service_count": self.service_count,
            "web_origin_count": self.web_origin_count,
            "endpoint_count": self.endpoint_count,
            "profile_confidence": round(self.profile_confidence, 4),
        }
