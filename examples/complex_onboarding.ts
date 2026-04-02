// ──────────────────────────────────────────────────────────────
// AXON Generated TypeScript v0.2  —  DO NOT EDIT BY HAND
// Guarantees: semantic validation · auto-parallelism · rollback
// ──────────────────────────────────────────────────────────────

export class AxonTypeError extends Error {
  constructor(msg: string) { super(msg); this.name = "AxonTypeError"; }
}
export class AxonFaultError extends Error {
  constructor(public readonly code: string, public readonly context?: unknown) {
    super(`[AXON FAULT] ${code}`); this.name = "AxonFaultError";
  }
}

export interface UserRecord  { id: string; email: string; balance: number; [k: string]: unknown; }
export interface OrderRecord { id: string; userId: string; total: number; status: string; [k: string]: unknown; }
export interface CartItem    { id: string; price: number; quantity: number; sku: string; }

declare const db: Record<string, {
  findOne: (q: Record<string, unknown>) => Promise<unknown>;
  create:  (d: Record<string, unknown>) => Promise<unknown>;
  update:  (q: Record<string, unknown>, d: Record<string, unknown>) => Promise<unknown>;
  delete:  (q: Record<string, unknown>) => Promise<void>;
}>;
declare const notify: { send: (to: string, tpl: string) => Promise<void>; };
declare const mcp:    Record<string, Record<string, (a: unknown) => Promise<unknown>>>;
declare const human:  { approve: (p: string) => Promise<boolean>; input: (p: string) => Promise<string>; };

export class Identity {
  public fullName: string;
  public idNumber: string;
  public country: string;

  constructor(data: any) {
    this.fullName = data.fullName;
    this.idNumber = data.idNumber;
    this.country = data.country;
  }
}

export class Profile {
  public email: string;
  public verified: boolean;
  public tier: string;

  constructor(data: any) {
    this.email = data.email;
    if (!/^[^@]+@[^@]+\.[^@]+$/.test(this.email)) throw new AxonTypeError("Invalid email_address: Profile.email");
    this.verified = data.verified;
    this.tier = data.tier;
  }
}

export async function verify_identity(
  inputs: { id: Identity }
): Promise<boolean> {
  // ── Semantic input validation ─────────────────────────────────

  const results: Record<string, unknown> = {};
  const rollbackStack: Array<() => Promise<void>> = [];

  try {
    // ── NODE scan_document ─────────────────────────────────
    const scan_document_raw: unknown = await mcp.vision.scan({ docId: inputs.id.idNumber });
    const scan_document_result: string = scan_document_raw as string;
    results.scan_document = scan_document_result;

    // ── NODE manual_check ──────────────────────────────────
    if ((results.scan_document as string) === "flagged") {
      const manual_check_raw: unknown = await human.approve("High risk document flagged. Approve?");
      const manual_check_result: boolean = manual_check_raw as boolean;
      results.manual_check = manual_check_result;
    }

    return results.manual_check as boolean;
  } catch (err) {
    throw err;
  }
}

export async function onboarding_flow(
  inputs: { userEmail: string; age: number; ident: Identity }
): Promise<Profile> {
  // ── Semantic input validation ─────────────────────────────────
  if (!/^[^@]+@[^@]+\.[^@]+$/.test(inputs.userEmail)) throw new AxonTypeError("Invalid email_address: userEmail");

  const results: Record<string, unknown> = {};
  const rollbackStack: Array<() => Promise<void>> = [];

  try {
    // ── Parallel: [check_db, identity_check, set_tier] ──────────────────────────
    const [__check_db_r, __identity_check_r, __set_tier_r] = await Promise.all([
      db.users.findOne({ email: inputs.userEmail }),  // check_db
      (inputs.age >= 18) ? verify_identity({ id: inputs.ident }) : Promise.resolve(null),  // identity_check
      /* axon:MAP IN . age >= 18 -> adult , minor */ [],  // set_tier
    ]);
    const check_db_result: UserRecord = __check_db_r as UserRecord;
    results.check_db = check_db_result;
    if (check_db_result !== null) {
      throw new AxonFaultError("already_exists");
    }
    const identity_check_result: boolean = __identity_check_r as boolean;
    results.identity_check = identity_check_result;
    const set_tier_result: string = __set_tier_r as string;
    results.set_tier = set_tier_result;

    // ── NODE create_user ───────────────────────────────────
    const create_user_raw: unknown = await db.users.create({ email: inputs.userEmail, status: "active", verified: (results.identity_check as boolean), tier: (results.set_tier as string) });
    const create_user_result: Profile = create_user_raw as Profile;
    results.create_user = create_user_result;
    rollbackStack.push(async () => { await db.users.delete({ email: inputs.userEmail }); });

    return results.create_user as Profile;
  } catch (err) {
    for (const undo of [...rollbackStack].reverse()) {
      try { await undo(); }
      catch (e) { console.error('[AXON rollback]', e); }
    }
    throw err;
  }
}
