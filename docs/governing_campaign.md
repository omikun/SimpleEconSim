# Governing Egypt through its people

You govern Egypt during a food and debt crisis. People need meals and must pay taxes. Grain owners want payment for their stocks. Creditors want debt service. Your treasury and public grain are limited.

Choose policies, then press **Next**. People react on their own. You do not need to recruit individuals, arrange rallies or keep clicking an organizing button.

```sh
venv/bin/python -m client.desktop.app --scenario egypt-1877 --ui-mode guided --governing-network governing
```

## Read the screen

**People and policy**, over the terrain, shows who is underfed, unpaid taxes, private grain and owner losses. Its footer distinguishes people currently in network walkouts from those planning one next turn. The explanation below gives a recent concrete reason for participation changing. Hide the panel to see more terrain; the simulation continues.

**Governing Egypt**, on the right, shows the treasury, grain stocks, the next debt deadline and your choices. You have the campaign's existing **one major decision per turn**. You can advance without spending it. **All policies** opens the fuller campaign controls; scroll that list and use **Back to governing** to return. Urgent creditor, political or military choices use the existing crisis dialogs. Answer those to continue; diplomatic replies follow their existing action rules.

An **organized demand** is a petition by actual people who want food or tax relief. A petition alone does not remove anyone from work. Some petitioners may join a **walkout** next turn. They need enough shared pressure and organization, work they can withhold, and enough resources to hold out. A very poor person can remain dissatisfied while being unable to afford a strike.

Food and tax cards can include the same person. That does not create another resident or make their work count twice. The cards point to the district with the most petitioners for that demand; a local response applies there, rather than magically settling the whole country.

## A first sequence to try

1. **Distribute maize** from the public reserve. The button shows the funded household meals and grain cost. This reserves next-turn food for selected underfed people. Buying grain and feeding people are separate decisions.
2. After advancing, compare three ways to reach private grain:
   - **Buy private maize** pays real owners from the treasury and moves their grain into public stores. You must distribute those stores on a later turn. Spending here leaves less for debt.
   - **Requisition maize** takes owners' actual stocks without paying them. Distribution is still necessary. Owner opposition grows from the seizure; it is not free political cooperation.
   - **Open private sales** permits standing sales. Buyers still need money, so people can remain hungry even with a functioning market.
3. Advance and check delivered food and walkouts. Acquiring grain alone does not resolve hunger. A person already funded for a full next meal can cancel their planned food walkout before production starts.
4. When a demand matters, consider its local response. **Seek funded worker terms** asks local owners to pay petitioners and raise wage offers. Individuals can reject the terms. An accepted ceasefire is temporary and can break if conditions worsen. **Forgive local tax arrears** writes off real unpaid balances; it does not also provide food.
5. Keep the debt date in view. When due, the main panel offers payment, revenue concession, deferral and default, with their costs and consequences. Default keeps cash but damages legitimacy and creditor relations. Wider fiscal and diplomatic options remain under **All policies**.

These steps demonstrate the choices, rather than guarantee a winning campaign. A small relief reserve cannot feed everyone indefinitely. Judge the result by the existing campaign's food access, fiscal position and government control. You can protect creditors while households suffer, or gain public grain while alienating its owners.

## What the network adds

There is one small graph spanning districts. Its nodes are organizations with memberships drawn from the existing population, rather than a separate cast of simulated citizens. Contacts carry food and tax pressure between household associations. Local grain owners push against household claims. Shared contacts also make coordinated action easier. Personal needs, risk, experience of delivery and repression, and ability to survive without working determine who actually joins.

This first integration models household petitions and walkouts. Owner opposition affects competing pressure; merchants currently provide a material view rather than an independent bargaining system. Authored contacts are experimental scenario content. The system does not yet model every political relationship or add an opposition campaign after overthrow.

**Off** retains the original campaign. **Observe** shows the [read-only community view](governing_network_observation.md). **Governing** enables the responses described here. Choose a mode when creating a campaign; changing it requires a new campaign. Existing saves are not converted. Native checkpoints retain pending intentions, organization memory and independent strike causes.

See the [implementation contract](../planning/governing_network_ownership_register.md) and [verification report](../planning/reports/governing_network_governing.md) for technical boundaries and tested limits.
