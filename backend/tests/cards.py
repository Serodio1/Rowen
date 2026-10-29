"""Cards for the tests, shared by the test files that need the same ones."""

from rowen.engine.cards import Row, SpecialCard, SpecialKind, UnitCard

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
KNIGHT = UnitCard(id="knight", name="Knight", rows=(Row.MELEE,), strength=5)
SCOUT = UnitCard(id="scout", name="Scout", rows=(Row.MELEE,), strength=3)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
HOARFROST = SpecialCard(id="hoarfrost", name="Hoarfrost", kind=SpecialKind.HOARFROST)
