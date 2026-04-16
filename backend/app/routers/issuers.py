"""Issuer endpoints."""

from fastapi import APIRouter, Depends

from ..schemas import IssuerRead, IssuerApplicationRuleRead
from ..services import IssuerService, get_issuer_service

router = APIRouter(tags=["issuers"])


@router.get("/issuers", response_model=list[IssuerRead])
async def list_issuers(
    issuer_service: IssuerService = Depends(get_issuer_service),
):
    return await issuer_service.list_all()


@router.get("/issuers/application-rules", response_model=list[IssuerApplicationRuleRead])
async def list_issuer_application_rules(
    issuer_service: IssuerService = Depends(get_issuer_service),
):
    """List all known issuer velocity/eligibility rules (e.g. Chase 5/24, Amex 1/90)."""
    return await issuer_service.list_application_rules()
