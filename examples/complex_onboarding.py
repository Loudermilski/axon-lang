# ──────────────────────────────────────────────────────────────
# AXON Generated Python  —  DO NOT EDIT BY HAND
# Guarantees: semantic validation · auto-parallelism · rollback
# ──────────────────────────────────────────────────────────────

from __future__ import annotations
import asyncio
import re
from typing import Any


class AxonTypeError(Exception):
    pass


class AxonFaultError(Exception):
    def __init__(self, code: str, context: Any = None):
        super().__init__(f'[AXON FAULT] {code}')
        self.code = code
        self.context = context


def axon_assert(condition: bool, description: str) -> None:
    if not condition:
        raise AxonFaultError('assertion_failed', {'condition': description})

class HumanUtility:
    async def approve(self, prompt: str) -> bool: return True
    async def input(self, prompt: str) -> str: return ''
human = HumanUtility()

class Identity:
    def __init__(self, data: dict):
        self.fullName = data.get('fullName')
        self.idNumber = data.get('idNumber')
        self.country = data.get('country')

    @classmethod
    def from_dict(cls, data: dict) -> Identity:
        return cls(data)

class Profile:
    def __init__(self, data: dict):
        self.email = data.get('email')
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", self.email): raise AxonTypeError("Invalid email_address: Profile.email")
        self.verified = data.get('verified')
        self.tier = data.get('tier')

    @classmethod
    def from_dict(cls, data: dict) -> Profile:
        return cls(data)

async def verify_identity(inputs: dict[str, Any]) -> bool:
    # ── Semantic input validation ─────────────────────────────────

    results: dict[str, Any] = {}
    rollback_stack: list = []

    try:
        # ── NODE scan_document ─────────────────────────────────
        scan_document_raw = await mcp['vision']['scan']({'docId': inputs.get('id')})
        results['scan_document'] = scan_document_raw

        # ── NODE manual_check ──────────────────────────────────
        if results['scan_document'] == "flagged":
            manual_check_raw = await human.approve("High risk document flagged. Approve?")
            results['manual_check'] = manual_check_raw

        return results['manual_check']
    except Exception as err:
        raise

async def onboarding_flow(inputs: dict[str, Any]) -> dict:
    # ── Semantic input validation ─────────────────────────────────
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", inputs.get('userEmail')): raise AxonTypeError("Invalid email_address: userEmail")

    results: dict[str, Any] = {}
    rollback_stack: list = []

    try:
        # ── Parallel: [check_db, identity_check, set_tier] ──────────────────────────
        async def __check_db_task():
            return await db['users'].find_one({'email': inputs.get('userEmail')})
        async def __identity_check_task():
            if inputs.get('age') >= 18:
                return await verify_identity({'id': inputs.get('ident')})
            return None
        async def __set_tier_task():
            return adult if inputs.get('age') >= 18 else minor
        __check_db_r, __identity_check_r, __set_tier_r = await asyncio.gather(__check_db_task(), __identity_check_task(), __set_tier_task())
        results['check_db'] = __check_db_r
        if results['check_db'] != None:
            raise AxonFaultError('already_exists')
        results['identity_check'] = __identity_check_r
        results['set_tier'] = __set_tier_r

        # ── NODE create_user ───────────────────────────────────
        create_user_raw = await db['users'].create({'email': inputs.get('userEmail'), 'status': 'active', 'verified': results['identity_check'], 'tier': results['set_tier']})
        results['create_user'] = create_user_raw
        async def __rollback_create_user():
            await db['users'].delete({'email': inputs.get('userEmail')})
        rollback_stack.append(__rollback_create_user)

        return results['create_user']
    except Exception as err:
        for undo in reversed(rollback_stack):
            try:
                await undo()
            except Exception as e:
                print(f'[AXON rollback] {e}')
        raise
