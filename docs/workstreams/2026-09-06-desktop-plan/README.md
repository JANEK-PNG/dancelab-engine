# Desktop implementation planning

Start with [the populated implementation plan](PLAN_WDROZENIA.md). It follows the
six-step structure agreed with the owner: product boundaries, current function
map, user journeys, GUI structure, integration contracts and ordered work packages.

The plan is grounded in code at `d5333c2`, native-window observations and a
read-only inventory of the actual library and saved state. All proposals and
estimates are labelled separately from observations and measurements.

- [Native observations](OBSERVATIONS.md)
- [Planning decisions](DECYZJE.md)
- [Verification and limitations](VERIFICATION.md)
- [Measured inventory](evidence/inventory.json)
- [Public bridge signatures](evidence/bridge-inventory.json)
- [Short session report](RAPORT.md)

The only code change in this planning increment isolates a pre-existing test
from the personal current-plan pointer. Product implementation remains scheduled
in the plan rather than implicitly marked complete.
