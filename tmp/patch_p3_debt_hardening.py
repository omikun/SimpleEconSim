"""Phase 3: debt-inheritance write-down hardening (option b).

For an agent dying with unpaid loans and no heirs, the *full forgiven
principle R* must be written off deposits (L -= R already happened above; the
audit total requires an offsetting D -= R).  A gov bailout cushions the pool
first (gov cash -> deposits; both are audited, so it is conserved), letting
depositors effectively absorb only the residual R - actual.

If R still exceeds deposits after the bailout injection, deposits would go
negative — a genuine insolvency.  That should never happen; we dump a full
diagnostic trace and raise instead of silently destroying money.
"""
p = "/Users/sli/Code/econsim_live.py"
src = open(p).read()

old = """        if len(living_descendants) > 0:
            principle_share = remaining_principle / len(living_descendants)
            for descendent in living_descendants:
                new_loan = trade.Loan(ctx.bank, descendent, principle_share,
                                      ctx.bank.interest_rate)
                descendent.loans.append(new_loan)
                ctx.bank.loans.append(new_loan)
                ctx.bank.total_liabilities += principle_share
        else:
            # Write down only what deposits can absorb. If bailout fails,
            # the excess bad debt is absorbed as a liability write-down
            # (equity stays zero rather than going negative).
            write_down = min(remaining_principle, ctx.bank.total_deposits)
            if remaining_principle > ctx.bank.total_deposits:
                bailout_ok = ctx.bank.RequestBailout(t, remaining_principle)
                if bailout_ok:
                    write_down = min(remaining_principle, ctx.bank.total_deposits)
                else:
                    # Bailout failed — write down excess as lost liabilities
                    excess = remaining_principle - ctx.bank.total_deposits
                    ctx.bank.total_liabilities -= excess
                    loginfo(t, f"Bailout failed: write down ${excess:.2f} "
                            f"in liabilities (no government funds)")
            ctx.bank.total_deposits -= write_down"""
new = """        if len(living_descendants) > 0:
            principle_share = remaining_principle / len(living_descendants)
            for descendent in living_descendants:
                new_loan = trade.Loan(ctx.bank, descendent, principle_share,
                                      ctx.bank.interest_rate)
                descendent.loans.append(new_loan)
                ctx.bank.loans.append(new_loan)
                ctx.bank.total_liabilities += principle_share
        else:
            # Phase 3 (option b): conservation-safe forgiveness.
            # The loan was already forgiven above (total_liabilities -= R).
            # To keep the audited total (agent cash + deposits - liabilities)
            # unchanged, the deposit pool MUST be written down by the FULL R.
            # A government bailout cushions the pool first (gov cash -> bank
            # deposits; both audited, so conserved), letting depositors absorb
            # only R - actual.  If R still exceeds deposits after the
            # injection, deposits would go negative -> genuine insolvency:
            # raise with a diagnostic trace rather than silently destroy money.
            if remaining_principle > ctx.bank.total_deposits:
                # RequestBailout moves real gov cash into deposits (conserved)
                bailout_ok = ctx.bank.RequestBailout(t, remaining_principle)
                if bailout_ok:
                    logwarning(t, f"GOV BAILOUT injected funds covering "
                                  f"${remaining_principle - ctx.bank.total_deposits:.2f} "
                                  f"of ${remaining_principle:.2f} forgiven bad debt; "
                                  f"depositors protected by gov capital")
            if remaining_principle > ctx.bank.total_deposits:
                _raise_insolvency(t, ctx.bank, agent, remaining_principle)
            ctx.bank.total_deposits -= remaining_principle"""
assert old in src, "no-heirs-anchor"
src = src.replace(old, new)

# ---- 2. Add the insolvency diagnostic raise (before _zero_out_dead_agent) ----
old = """def _zero_out_dead_agent(ctx: LiveContext, agent):"""
new = """def _raise_insolvency(t, bank, agent, shortfall):
    \"\"\"Raise when a write-down would push deposits below zero.

    Indicates the bank cannot absorb a forgiven loan even after government
    bailout — a genuine insolvency.  Refuse to silently destroy money; dump
    enough state to debug what caused it.
    \"\"\"
    import sys
    import traceback
    outstanding = sum((l.principle - l.principle_paid) for l in bank.loans)
    agent_owed = sum((l.principle - l.principle_paid) for l in agent.loans)
    gov_cash = getattr(getattr(bank, 'gov', None), 'agent', None)
    gov_cash = gov_cash.cash if gov_cash is not None else None
    print(f"\\n=== BANK INSOLVENCY DETECTED (write-down would make deposits negative) ===",
          file=sys.stderr)
    print(f"  turn={t}  shortfall=${shortfall:.2f}", file=sys.stderr)
    print(f"  bank: total_deposits={bank.total_deposits:.2f} "
          f"total_liabilities={bank.total_liabilities:.2f} "
          f"equity={bank.total_deposits - bank.total_liabilities:.2f}",
          file=sys.stderr)
    print(f"  bank loans outstanding=${outstanding:.2f} ({len(bank.loans)} loans)",
          file=sys.stderr)
    print(f"  dying agent id={agent.id} cash={agent.cash:.2f} "
          f"deposits={bank.deposits.get(agent, 0):.2f} "
          f"loans owed=${agent_owed:.2f} ({len(agent.loans)} loans) "
          f"age={t - agent.birth_round}", file=sys.stderr)
    print(f"  gov cash={gov_cash}", file=sys.stderr)
    print(f"  fx_pool={bank.fx_pool:.2f} "
          f"foreign_reserves={dict(bank.foreign_reserves)}", file=sys.stderr)
    traceback.print_stack()
    raise RuntimeError(
        "BANK INSOLVENCY: write-down would make deposits negative; "
        "see stderr for full attribution trace")


def _zero_out_dead_agent(ctx: LiveContext, agent):"""
assert old in src, "raise-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("debt write-down hardening applied (conserved full-R haircut)")