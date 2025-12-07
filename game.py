"""Text-based wrestling career simulation.

The game models a wrestler progressing from youth through post-college
careers with weekly turn-based actions.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple


SAVE_FILE = Path("savegame.json")


class CareerStage(Enum):
    YOUTH = auto()
    JUNIOR_HIGH = auto()
    HIGH_SCHOOL = auto()
    COLLEGE = auto()
    POST_COLLEGE = auto()


class WeightClassSystem(Enum):
    YOUTH = auto()
    PIAA = auto()
    NCAA = auto()


WEIGHT_CLASSES: Dict[WeightClassSystem, List[int]] = {
    WeightClassSystem.YOUTH: [60, 70, 80, 90, 100, 110],
    WeightClassSystem.PIAA: [107, 114, 121, 127, 133, 139, 145, 152, 160, 172, 189, 215, 285],
    WeightClassSystem.NCAA: [125, 133, 141, 149, 157, 165, 174, 184, 197, 285],
}


class InjurySeverity(Enum):
    CATASTROPHIC = auto()
    MAJOR = auto()
    MODERATE = auto()
    MINOR = auto()


SEVERITY_DURATION: Dict[InjurySeverity, Tuple[int, int]] = {
    InjurySeverity.CATASTROPHIC: (52, 999),
    InjurySeverity.MAJOR: (8, 17),
    InjurySeverity.MODERATE: (3, 7),
    InjurySeverity.MINOR: (1, 2),
}


@dataclass
class Injury:
    name: str
    severity: InjurySeverity
    remaining_weeks: int
    stat_penalty: int

    def tick(self) -> None:
        if self.remaining_weeks > 0:
            self.remaining_weeks -= 1

    @property
    def is_active(self) -> bool:
        return self.remaining_weeks > 0


@dataclass
class Finance:
    money: int = 0
    income_history: List[str] = field(default_factory=list)
    expense_history: List[str] = field(default_factory=list)

    def add_income(self, amount: int, reason: str) -> None:
        self.money += amount
        self.income_history.append(f"+${amount}: {reason}")

    def add_expense(self, amount: int, reason: str) -> None:
        self.money -= amount
        self.expense_history.append(f"-${amount}: {reason}")


@dataclass
class Stats:
    strength: int = 40
    speed: int = 40
    stamina: int = 40
    technique: int = 40
    mentality: int = 40
    toughness: int = 40
    confidence: int = 40

    def clamp(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            setattr(self, field_name, max(0, min(100, value)))


@dataclass
class Record:
    wins: int = 0
    losses: int = 0
    pins: int = 0
    majors: int = 0
    decisions: int = 0

    def log_result(self, outcome: "MatchOutcome") -> None:
        if outcome.is_win:
            self.wins += 1
        else:
            self.losses += 1

        if outcome.pinned:
            self.pins += 1
        elif outcome.major:
            self.majors += 1
        else:
            self.decisions += 1


@dataclass
class Player:
    name: str
    hometown: str = "Pennsylvania"
    age: int = 6
    grade: int = 1
    career_stage: CareerStage = CareerStage.YOUTH
    weight_class: int = WEIGHT_CLASSES[WeightClassSystem.YOUTH][0]
    stats: Stats = field(default_factory=Stats)
    fatigue: int = 10
    injury_risk: int = 5
    injuries: List[Injury] = field(default_factory=list)
    finance: Finance = field(default_factory=Finance)
    record: Record = field(default_factory=Record)
    achievements: List[str] = field(default_factory=list)
    weight_cut_pressure: int = 0

    def weekly_reset(self) -> None:
        self.stats.clamp()
        self.fatigue = max(0, min(100, self.fatigue))
        self.injury_risk = max(1, min(95, self.injury_risk))
        for injury in self.injuries:
            injury.tick()
        self.injuries = [injury for injury in self.injuries if injury.is_active]

    def active_injury_penalty(self) -> int:
        return sum(injury.stat_penalty for injury in self.injuries if injury.is_active)

    def current_weight_classes(self) -> List[int]:
        if self.career_stage == CareerStage.YOUTH:
            return WEIGHT_CLASSES[WeightClassSystem.YOUTH]
        if self.career_stage == CareerStage.HIGH_SCHOOL or self.career_stage == CareerStage.JUNIOR_HIGH:
            return WEIGHT_CLASSES[WeightClassSystem.PIAA]
        return WEIGHT_CLASSES[WeightClassSystem.NCAA]

    def adjust_weight_class(self, target: int) -> str:
        if target not in self.current_weight_classes():
            return "Invalid weight class for current level."
        risk_spike = abs(target - self.weight_class) // 5
        self.weight_class = target
        self.weight_cut_pressure = min(100, self.weight_cut_pressure + risk_spike)
        self.fatigue = min(100, self.fatigue + risk_spike)
        self.injury_risk = min(95, self.injury_risk + risk_spike // 2)
        return f"Moved to {target} weight class; cut pressure now {self.weight_cut_pressure}."

    def apply_action(self, action: str) -> str:
        message = ""
        if action == "strength":
            gain = random.randint(1, 2)
            self.stats.strength += gain
            self.fatigue += 8
            self.injury_risk += 2
            self.finance.add_expense(10, "Weight room access")
            message = f"Strength increased by {gain}."
        elif action == "technique":
            gain = random.randint(1, 3)
            self.stats.technique += gain
            self.stats.mentality += 1
            self.fatigue += 6
            self.finance.add_expense(15, "Club practice")
            message = f"Technique increased by {gain}."
        elif action == "film":
            self.stats.technique += 1
            self.stats.confidence += 1
            self.fatigue += 3
            self.finance.add_expense(5, "Film subscription")
            message = "Studied film and improved awareness."
        elif action == "condition":
            self.stats.stamina += 1
            self.stats.speed += 1
            self.fatigue += 7
            self.finance.add_expense(5, "Running shoes")
            message = "Conditioning improved stamina and speed."
        elif action == "rest":
            recovered = random.randint(8, 15)
            self.fatigue = max(0, self.fatigue - recovered)
            self.injury_risk = max(1, self.injury_risk - 2)
            message = f"Rested and recovered {recovered} fatigue."
        elif action == "recover":
            if not self.injuries:
                message = "No injuries to rehab."
            else:
                for injury in self.injuries:
                    injury.remaining_weeks = max(0, injury.remaining_weeks - 1)
                self.fatigue = max(0, self.fatigue - 5)
                self.finance.add_expense(25, "Physical therapy")
                message = "Spent the week rehabbing injuries."
        elif action == "weight":
            reduction = random.randint(1, 4)
            self.weight_cut_pressure = max(0, self.weight_cut_pressure - reduction)
            self.fatigue += 4
            self.injury_risk += 1
            message = f"Managed weight; cut pressure lowered by {reduction}."
        elif action == "equipment":
            self.finance.add_expense(50, "New headgear and shoes")
            self.stats.confidence += 2
            message = "Purchased equipment boosting morale."
        elif action == "coach":
            self.finance.add_expense(75, "Private coach session")
            self.stats.technique += 2
            self.stats.mentality += 1
            self.fatigue += 5
            message = "Private coaching refined technique."
        elif action == "nil":
            if self.career_stage in {CareerStage.HIGH_SCHOOL, CareerStage.COLLEGE} and self.grade >= 12:
                earnings = random.randint(50, 150)
                self.finance.add_income(earnings, "Local NIL appearance")
                self.stats.confidence += 1
                message = f"Secured a small NIL deal worth ${earnings}."
            else:
                message = "Not eligible for NIL at this stage."
        else:
            message = "Unknown action."

        self.weekly_reset()
        return message

    def season_progression(self) -> None:
        self.age += 1
        self.grade += 1
        if self.grade <= 6:
            self.career_stage = CareerStage.YOUTH
        elif self.grade <= 8:
            self.career_stage = CareerStage.JUNIOR_HIGH
        elif self.grade <= 12:
            self.career_stage = CareerStage.HIGH_SCHOOL
        elif self.grade <= 16:
            self.career_stage = CareerStage.COLLEGE
        else:
            self.career_stage = CareerStage.POST_COLLEGE

        # Update weight class band to closest option in new system
        classes = self.current_weight_classes()
        closest = min(classes, key=lambda c: abs(c - self.weight_class))
        self.weight_class = closest
        if self.career_stage == CareerStage.COLLEGE and self.grade == 13:
            self.finance.add_income(500, "Scholarship stipend")


@dataclass
class Opponent:
    name: str
    tier: str
    stats: Stats

    @staticmethod
    def generate_for_stage(stage: CareerStage) -> "Opponent":
        base = {
            CareerStage.YOUTH: 35,
            CareerStage.JUNIOR_HIGH: 45,
            CareerStage.HIGH_SCHOOL: 55,
            CareerStage.COLLEGE: 65,
            CareerStage.POST_COLLEGE: 70,
        }[stage]
        spread = random.randint(0, 20)
        stats = Stats(
            strength=base + random.randint(0, spread),
            speed=base + random.randint(0, spread),
            stamina=base + random.randint(0, spread),
            technique=base + random.randint(0, spread),
            mentality=base + random.randint(0, spread // 2),
            toughness=base + random.randint(0, spread // 2),
            confidence=base,
        )
        stats.clamp()
        tier = random.choice(["local", "district", "regional", "state", "national"])
        return Opponent(name="Tough Rival", tier=tier, stats=stats)


@dataclass
class MatchOutcome:
    result: str
    pinned: bool = False
    major: bool = False

    @property
    def is_win(self) -> bool:
        return self.result.startswith("Win")


class Match:
    def __init__(self, player: Player, opponent: Opponent):
        self.player = player
        self.opponent = opponent

    def simulate(self) -> MatchOutcome:
        penalty = self.player.active_injury_penalty()
        player_score = (
            self.player.stats.strength
            + self.player.stats.technique
            + self.player.stats.speed
            + self.player.stats.stamina
            + self.player.stats.mentality
            - self.player.fatigue
            - penalty
        )
        opp_score = (
            self.opponent.stats.strength
            + self.opponent.stats.technique
            + self.opponent.stats.speed
            + self.opponent.stats.stamina
            + self.opponent.stats.mentality
        )
        variability = random.randint(-20, 20)
        player_score += variability
        threshold = opp_score + random.randint(-10, 10)

        if player_score - threshold > 20:
            outcome = MatchOutcome("Win by pin", pinned=True)
        elif player_score > threshold + 10:
            outcome = MatchOutcome("Win by major decision", major=True)
        elif player_score > threshold:
            outcome = MatchOutcome("Win by decision")
        elif threshold - player_score > 20:
            outcome = MatchOutcome("Loss by pin", pinned=True)
        elif threshold > player_score + 10:
            outcome = MatchOutcome("Loss by major decision", major=True)
        else:
            outcome = MatchOutcome("Loss by decision")

        self.player.record.log_result(outcome)
        self.player.stats.confidence += 2 if outcome.is_win else -2
        self.player.stats.confidence = max(0, min(100, self.player.stats.confidence))
        return outcome


@dataclass
class Tournament:
    name: str
    level: str
    bracket_size: int = 8

    def run(self, player: Player) -> str:
        wins = 0
        losses = 0
        for _ in range(self.bracket_size // 2):
            opponent = Opponent.generate_for_stage(player.career_stage)
            outcome = Match(player, opponent).simulate()
            if outcome.is_win:
                wins += 1
            else:
                losses += 1
                break  # single elimination for simplicity
        placement = "Champion" if losses == 0 else f"{wins} wins"
        player.achievements.append(f"{self.level} {self.name}: {placement}")
        return f"Tournament {self.name} ({self.level}) result: {placement}."


@dataclass
class Season:
    player: Player
    week: int = 1
    in_season: bool = False
    postseason_phase: Optional[str] = None
    recruitment_interest: int = 0

    def toggle_season(self) -> None:
        self.in_season = not self.in_season
        if not self.in_season:
            self.postseason_phase = None

    def advance_week(self) -> None:
        self.week += 1
        self.player.weekly_reset()
        if self.week % 52 == 0:
            self.player.season_progression()
            self.recruitment_interest += max(0, self.player.record.wins - self.player.record.losses)
            self.in_season = False
            self.postseason_phase = None

    def determine_postseason(self) -> Optional[Tournament]:
        if not self.in_season:
            return None
        phases = ["Districts", "Regionals", "States"] if self.player.career_stage in {CareerStage.HIGH_SCHOOL, CareerStage.JUNIOR_HIGH} else ["Conference", "NCAA"]
        if self.postseason_phase is None:
            self.postseason_phase = phases[0]
        else:
            idx = phases.index(self.postseason_phase)
            if idx + 1 < len(phases):
                self.postseason_phase = phases[idx + 1]
            else:
                return None
        return Tournament(name=self.postseason_phase, level=self.player.career_stage.name)


class SaveLoadSystem:
    @staticmethod
    def save(player: Player, season: Season) -> None:
        data = {
            "player": asdict(player),
            "season": {
                "week": season.week,
                "in_season": season.in_season,
                "postseason_phase": season.postseason_phase,
                "recruitment_interest": season.recruitment_interest,
            },
            "career_stage": player.career_stage.name,
        }
        data["player"]["career_stage"] = player.career_stage.name
        data["player"]["injuries"] = [
            {
                "name": inj.name,
                "severity": inj.severity.name,
                "remaining_weeks": inj.remaining_weeks,
                "stat_penalty": inj.stat_penalty,
            }
            for inj in player.injuries
        ]
        with SAVE_FILE.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    @staticmethod
    def load() -> Optional[Tuple[Player, Season]]:
        if not SAVE_FILE.exists():
            return None
        with SAVE_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        player_data = data["player"]
        stats = Stats(**player_data["stats"])
        finance = Finance(**player_data["finance"])
        record = Record(**player_data["record"])
        injuries = [
            Injury(
                name=item["name"],
                severity=InjurySeverity[item["severity"]],
                remaining_weeks=item["remaining_weeks"],
                stat_penalty=item["stat_penalty"],
            )
            for item in player_data.get("injuries", [])
        ]
        player = Player(
            name=player_data["name"],
            hometown=player_data.get("hometown", "Pennsylvania"),
            age=player_data["age"],
            grade=player_data["grade"],
            career_stage=CareerStage[player_data.get("career_stage", data["career_stage"])],
            weight_class=player_data["weight_class"],
            stats=stats,
            fatigue=player_data["fatigue"],
            injury_risk=player_data["injury_risk"],
            injuries=injuries,
            finance=finance,
            record=record,
            achievements=player_data.get("achievements", []),
            weight_cut_pressure=player_data.get("weight_cut_pressure", 0),
        )
        season_data = data["season"]
        season = Season(
            player=player,
            week=season_data["week"],
            in_season=season_data["in_season"],
            postseason_phase=season_data["postseason_phase"],
            recruitment_interest=season_data.get("recruitment_interest", 0),
        )
        return player, season


class RandomEvents:
    EVENTS = [
        ("illness", 0.05),
        ("bad_cut", 0.05),
        ("rival", 0.03),
        ("equipment_break", 0.04),
        ("recruiting_bump", 0.02),
    ]

    @staticmethod
    def trigger(player: Player, season: Season) -> Optional[str]:
        roll = random.random()
        cumulative = 0.0
        for name, prob in RandomEvents.EVENTS:
            cumulative += prob
            if roll < cumulative:
                return RandomEvents.apply(name, player, season)
        return None

    @staticmethod
    def apply(name: str, player: Player, season: Season) -> str:
        if name == "illness":
            penalty = random.randint(2, 5)
            player.stats.stamina = max(0, player.stats.stamina - penalty)
            player.fatigue = min(100, player.fatigue + 10)
            return "Caught a cold; stamina dipped temporarily."
        if name == "bad_cut":
            player.fatigue = min(100, player.fatigue + 15)
            player.injury_risk = min(95, player.injury_risk + 10)
            return "Rough weight cut increased fatigue and injury risk."
        if name == "rival":
            player.stats.confidence += 3
            return "A rival emerged, motivating harder training."
        if name == "equipment_break":
            player.finance.add_expense(30, "Replaced broken gear")
            return "Gear broke unexpectedly, costing money."
        if name == "recruiting_bump":
            season.recruitment_interest += 5
            return "Outstanding performance attracted college scouts."
        return ""


def render_status(player: Player, season: Season) -> str:
    lines = [
        f"Week {season.week} — Grade {player.grade} ({player.career_stage.name.title()})",
        f"Weight Class: {player.weight_class} | Fatigue: {player.fatigue} | Injury Risk: {player.injury_risk}%",
        f"Strength: {player.stats.strength}  Technique: {player.stats.technique}  Speed: {player.stats.speed}",
        f"Stamina: {player.stats.stamina}  Mentality: {player.stats.mentality}  Toughness: {player.stats.toughness}",
        f"Money: ${player.finance.money} | Record: {player.record.wins}-{player.record.losses} | Confidence: {player.stats.confidence}",
        f"Weight Cut Pressure: {player.weight_cut_pressure}",
    ]
    if player.injuries:
        lines.append("Active injuries: " + ", ".join(f"{inj.name} ({inj.severity.name})" for inj in player.injuries))
    if season.recruitment_interest:
        lines.append(f"Recruiting interest: {season.recruitment_interest}")
    return "\n".join(lines)


def weekly_menu() -> str:
    return (
        "Choose an action:\n"
        "1. Train technique (+1–3 tech, +fatigue)\n"
        "2. Strength training (+1–2 strength, +fatigue)\n"
        "3. Conditioning (+1 stamina/speed, +fatigue)\n"
        "4. Rest (-fatigue)\n"
        "5. Study film (+awareness)\n"
        "6. Manage weight\n"
        "7. Purchase equipment\n"
        "8. Private coach session\n"
        "9. Seek NIL/sponsorship (HS seniors & college)\n"
        "10. Enter dual meet (in season)\n"
        "11. Enter tournament (in season)\n"
        "12. Save game\n"
        "13. Quit\n"
    )


def process_choice(choice: str, player: Player, season: Season) -> Optional[str]:
    actions = {
        "1": "technique",
        "2": "strength",
        "3": "condition",
        "4": "rest",
        "5": "film",
        "6": "weight",
        "7": "equipment",
        "8": "coach",
        "9": "nil",
    }
    if choice in actions:
        return player.apply_action(actions[choice])
    if choice == "10":
        if not season.in_season:
            return "Dual meets only occur in season."
        opponent = Opponent.generate_for_stage(player.career_stage)
        outcome = Match(player, opponent).simulate()
        return f"Dual meet vs {opponent.tier} foe: {outcome.result}."
    if choice == "11":
        if not season.in_season:
            return "Tournaments only occur in season."
        tourney = Tournament(name="Local Open", level=player.career_stage.name)
        return tourney.run(player)
    if choice == "12":
        SaveLoadSystem.save(player, season)
        return "Game saved."
    if choice == "13":
        SaveLoadSystem.save(player, season)
        return None
    return "Invalid selection"


def apply_injury_risk(player: Player) -> Optional[str]:
    roll = random.randint(1, 100)
    if roll <= player.injury_risk:
        severity = random.choices(
            [InjurySeverity.MINOR, InjurySeverity.MODERATE, InjurySeverity.MAJOR, InjurySeverity.CATASTROPHIC],
            weights=[60, 25, 10, 5],
        )[0]
        duration_range = SEVERITY_DURATION[severity]
        duration = random.randint(*duration_range)
        penalty = {InjurySeverity.MINOR: 3, InjurySeverity.MODERATE: 8, InjurySeverity.MAJOR: 15, InjurySeverity.CATASTROPHIC: 100}[severity]
        injury = Injury(name=f"{severity.name.title()} injury", severity=severity, remaining_weeks=duration, stat_penalty=penalty)
        player.injuries.append(injury)
        if severity == InjurySeverity.CATASTROPHIC:
            player.achievements.append("Career ended due to injury")
        return f"Injury occurred: {injury.name} lasting {duration} weeks."
    return None


def main() -> None:
    loaded = SaveLoadSystem.load()
    if loaded:
        player, season = loaded
    else:
        player = Player(name="New Wrestler")
        season = Season(player=player)

    print("Welcome to Wrestling Life Simulator!")

    while True:
        print("\n" + render_status(player, season))
        event_msg = RandomEvents.trigger(player, season)
        if event_msg:
            print(f"Random event: {event_msg}")
        injury_msg = apply_injury_risk(player)
        if injury_msg:
            print(injury_msg)
            if any(inj.severity == InjurySeverity.CATASTROPHIC for inj in player.injuries):
                break

        print("\n" + weekly_menu())
        choice = input("Action: ").strip()
        result = process_choice(choice, player, season)
        if result is None and choice == "13":
            print("Saved and exiting. Thanks for playing!")
            break
        if result:
            print(result)
        season.advance_week()


if __name__ == "__main__":
    main()
