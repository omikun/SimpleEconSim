# Commonweal — Agent Guide

Rules inherited from the parent SimpleEconSim project (`../agent.md`), kept here:
1. **Conservation first.** Money and food move only through `World.pay()` / explicit flows; every tick
   `World.audit()` must pass. Any deliberate sink must be documented.
2. **No scripted crises.** Events must come from mechanisms (weather → stocks → debt → foreclosure). Presets
   only change the environment (outside buyers, outside tax), never trigger outcomes.
3. **Never run scripts from inline strings** — write a file first (use `tmp/`), then run it.
4. Commit messages go in a file and `git commit -F`; **commit, never push**.
5. Use the shared venv: `/Users/sli/Code/venv/bin/python`.

Project-specific:
- Thesis test: a system belongs only if it moves growth or health / wellbeing / culture.
- Stages of a tick are the `_stage` methods called in order from `World.step()`.
- Tuning workflow: `python run_sim.py 150 <seed> <preset>`; check tests, then multiple seeds.
- Baseline must stay livable (`test_livable_baseline`): high health, few work hours, no hunger in years 0–10.
