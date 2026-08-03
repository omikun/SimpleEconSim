"""Small patch: add FX desk summary to the final per-region printout."""

p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

old = '              f"ROI: {trader_roi:.1f}% (${init_trader_cash:.0f}->${final_trader_cash:.0f})")\n\n    print("\\nDone.")'
new = """              f"ROI: {trader_roi:.1f}% (${init_trader_cash:.0f}->${final_trader_cash:.0f})")

        desk = getattr(region, "forex", None)
        if desk is not None:
            bank = region.bank
            print(f"  FX Desk: mid={desk.mid:.4f} ({region.home_currency} per 1 "
                  f"{desk.other}), spread={desk.spread:.2%}, "
                  f"reserves={ {k: round(v, 2) for k, v in dict(bank.foreign_reserves).items()} }, "
                  f"fx_pool=${bank.fx_pool:.2f}")

    print("\\nDone.")"""

assert old in src, "MISSING summary anchor"
src = src.replace(old, new)
open(p, "w").write(src)
print("summary patch applied")