#!/usr/bin/env python3
# Phase 6D2: pass PPP target (partner/home basket-cost ratio) to desk.update
TARGET = 'econsim_two_region.py'
src = open(TARGET).read()

old = "    desk = getattr(region, 'forex', None)\n" \
      "    if desk is not None:\n" \
      "        desk.update(0, bank=getattr(region, 'bank', None),\n" \
      "                    fx_regime=getattr(region.gov, 'fx_regime', 'managed'))\n" \
      "        desk.save_rate(region)\n" \
      "        return region.exchange_rate\n"

new = "    desk = getattr(region, 'forex', None)\n" \
      "    if desk is not None:\n" \
      "        # PPP anchor: basket cost in partner / basket cost at home.\n" \
      "        partner = region.destination_region\n" \
      "        ppp = 1.0\n" \
      "        if partner is not None:\n" \
      "            home_col = max(0.1, region.cost_of_living)\n" \
      "            partner_col = max(0.1, partner.cost_of_living)\n" \
      "            ppp = partner_col / home_col\n" \
      "        desk.update(0, bank=getattr(region, 'bank', None),\n" \
      "                    fx_regime=getattr(region.gov, 'fx_regime', 'managed'),\n" \
      "                    ppp_target=ppp)\n" \
      "        desk.save_rate(region)\n" \
      "        return region.exchange_rate\n"

assert src.count(old) == 1, "update_exchange_rate desk block not found"
src = src.replace(old, new)

open(TARGET, 'w').write(src)
print("patch_p6d2.py applied OK")