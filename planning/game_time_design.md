# Game time: agent years and seasonal cycles

The game deliberately uses **two clocks**. One turn advances every agent by
**one agent year** for age, career tenure, apprenticeship, reproduction, and
other lifecycle rules. The agriculture and weather simulation completes **one
seasonal cycle every ten turns**. Its displayed seasonal year is `turn // 10 +
1`, and its phase within that cycle is `turn % 10`.

These clocks are gameplay abstractions. A seasonal cycle is not the same unit
as an agent's lived year; do not convert agent age, career switching rates,
birth spacing, contract duration, or historical annual mobility evidence by
dividing or multiplying by ten. Historical rates are compared with one agent
turn, after matching the eligible population and occupation definition.

Use explicit names in new code and UI: **agent age (years)** and **seasonal
year/phase**. Keep the existing ten-phase production curve. Tests must show
that from turn 0 to 10 an agent ages ten years while the seasonal clock
advances one complete cycle. Avoid a generic `turns_per_year` constant that
would invite one subsystem to use the other clock accidentally.

Design consequence: residents born during a campaign mature over agent turns.
They remain dependents until the chosen work-entry age; their presence should
affect food demand and family resources without granting an infant a full adult
production job. Changing employer, doing seasonal work, and changing primary
occupation are separate events. A permanent occupation change should be rare
enough to matter but remain possible after land loss, firm closure, sustained
opportunity, migration, or coercion.
