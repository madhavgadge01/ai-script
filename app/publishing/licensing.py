from typing import Dict, Any, Optional

class LicensingAuditor:
    """
    Evaluates and enforces source licensing compliance for educational notes.
    Ensures that materials with non-commercial restrictions are never published as paid notes.
    """

    LICENSE_ORIGINAL_SYNTHESIS = "ORIGINAL_ACADEMIC_SYNTHESIS"
    LICENSE_CC_BY_NC_SA = "CC_BY_NC_SA_4.0"
    LICENSE_PROPRIETARY = "PROPRIETARY_UNAUTHORIZED"

    @classmethod
    def audit_unit_licensing(
        cls,
        subject_code: str,
        unit_number: int,
        content_source_type: str = "ORIGINAL_ACADEMIC_SYNTHESIS",
        intended_price: float = 25.0
    ) -> Dict[str, Any]:
        """
        Audits licensing permissions for a specific unit.
        """
        audit_result: Dict[str, Any] = {
            "subject_code": subject_code,
            "unit_number": unit_number,
            "source_type": content_source_type,
            "intended_price": intended_price,
            "commercial_allowed": False,
            "public_publication_allowed": False,
            "requires_free_pricing": False,
            "attribution_text": "",
            "audit_verdict": "BLOCKED",
            "reason": ""
        }

        if content_source_type == cls.LICENSE_ORIGINAL_SYNTHESIS:
            audit_result["commercial_allowed"] = True
            audit_result["public_publication_allowed"] = True
            audit_result["requires_free_pricing"] = False
            audit_result["attribution_text"] = (
                f"UniNotes Structured Study Guide for {subject_code} Unit {unit_number}. "
                "Synthesized independently from standard university computing curricula."
            )
            audit_result["audit_verdict"] = "AUTHORIZED_COMMERCIAL_AND_FREE"
            audit_result["reason"] = "Original educational synthesis. Safe for platform publication with pricing."

        elif content_source_type == cls.LICENSE_CC_BY_NC_SA:
            audit_result["attribution_text"] = (
                f"Source: eGyanKosh (IGNOU) - {subject_code} Unit {unit_number}. "
                "Distributed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)."
            )
            if intended_price > 0:
                audit_result["commercial_allowed"] = False
                audit_result["public_publication_allowed"] = False
                audit_result["requires_free_pricing"] = True
                audit_result["audit_verdict"] = "BLOCKED_COMMERCIAL_RESTRICTION"
                audit_result["reason"] = (
                    "Source material carries CC BY-NC-SA (Non-Commercial). "
                    "Cannot be published with non-zero price on Notes Guru. "
                    "Must be priced at ₹0 or retained in internal draft status."
                )
            else:
                audit_result["commercial_allowed"] = False
                audit_result["public_publication_allowed"] = True
                audit_result["requires_free_pricing"] = True
                audit_result["audit_verdict"] = "AUTHORIZED_FREE_ONLY"
                audit_result["reason"] = "CC BY-NC-SA material authorized for public redistribution at ₹0 (Free) with attribution."

        else:
            audit_result["commercial_allowed"] = False
            audit_result["public_publication_allowed"] = False
            audit_result["requires_free_pricing"] = False
            audit_result["audit_verdict"] = "BLOCKED_UNAUTHORIZED"
            audit_result["reason"] = "Source rights are proprietary or unverified. Republication strictly blocked."

        return audit_result
