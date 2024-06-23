from nurse_scheduling.types import (
    MonthScheduleDict,
    DayScheduleDict,
    ShiftScheduleDict,
)
from nurse_scheduling import utils
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar


if __name__ == "__main__":
    # Reading initial data
    args = utils.get_args()
    data = utils.load_shift_planning_data(args.path)
    num_days = len(data["days"])
    max_shifts = num_days * len(data["days"][0]["shifts"])

    # Model initialization
    model = cp_model.CpModel()

    # Variable initialization
    shift_slots: dict[tuple[int, int, int], IntVar] = {}
    for n in data["nurses"]:
        for d in data["days"]:
            for s in d["shifts"]:
                nurse = n["nurse_identifier"]
                day = d["day_of_month"]
                shift = s["shift_identifier"]
                shift_slots[(nurse, day, shift)] = model.new_bool_var(
                    f"shift_n{n}_d{d}_s{s}"
                )

    # Constraint: Each nurse works at most one shift per day
    # Constraint: Nurses shouldn't work if absence was requested
    # Constraint prepared: No nurse should work 4 days consecutively
    work_on_day: dict[tuple[int, int], IntVar] = {}
    for n in data["nurses"]:
        for d in data["days"]:
            nurse = n["nurse_identifier"]
            day = d["day_of_month"]
            model.add_at_most_one(
                shift_slots[(nurse, day, s["shift_identifier"])] for s in d["shifts"]
            )

            work_on_day[(nurse, day)] = model.new_bool_var(f"work_n{nurse}_d{day}")
            model.add_max_equality(
                work_on_day[(nurse, day)],
                [shift_slots[(nurse, day, s["shift_identifier"])] for s in d["shifts"]],
            )

            if d["day_of_month"] in n["days_off_requested"]:
                model.add(
                    sum(
                        shift_slots[(nurse, day, s["shift_identifier"])]
                        for s in d["shifts"]
                    )
                    == 0
                )

    # Constraint: No nurse should work 4 days consecutively
    for n in data["nurses"]:
        nurse = n["nurse_identifier"]
        for start_day in range(num_days - 3):
            # Create a list of work_on_day variables for the 4 consecutive days
            model.add(
                sum(
                    work_on_day[(nurse, data["days"][start_day + i]["day_of_month"])]
                    for i in range(4)
                )
                <= 3
            )

    # Constraint: Each shift on each day must have the required number of nurses
    for d in data["days"]:
        for s in d["shifts"]:
            day = d["day_of_month"]
            shift = s["shift_identifier"]
            model.add(
                sum(
                    shift_slots[(n["nurse_identifier"], day, shift)]
                    for n in data["nurses"]
                )
                == s["number_of_nurses_required"]
            )

    # Prepare additional variables for non-linear objective
    shift_counts: dict[int, IntVar] = {}
    shift_counts_squared: dict[int, IntVar] = {}
    for n in data["nurses"]:
        nurse = n["nurse_identifier"]
        shift_counts[nurse] = model.new_int_var(
            0,
            max_shifts,
            f"nurse_{nurse}_worked_shifts",
        )
        model.add(
            shift_counts[nurse]
            == sum(
                shift_slots[(nurse, day["day_of_month"], shift["shift_identifier"])]
                for day in data["days"]
                for shift in day["shifts"]
            )
        )
        shift_counts_squared[nurse] = model.new_int_var(
            0,
            max_shifts**2,
            f"nurse_{nurse}_worked_shifts",
        )
        model.add_multiplication_equality(
            shift_counts_squared[nurse], [shift_counts[nurse], shift_counts[nurse]]
        )

    # Objective
    model.minimize(
        sum(shift_counts_squared[n["nurse_identifier"]] for n in data["nurses"])
    )
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # Print + saving results
    if status == cp_model.OPTIMAL:
        schedule = MonthScheduleDict(
            {"year": data["year"], "month": data["month"], "days": []}
        )
        for d in data["days"]:
            day = d["day_of_month"]
            day_schedule = DayScheduleDict({"day_of_month": day, "shifts": []})
            schedule["days"].append(day_schedule)
            for s in d["shifts"]:
                shift = s["shift_identifier"]
                shift_schedule = ShiftScheduleDict(
                    {"shift_identifier": shift, "nurses": []}
                )
                day_schedule["shifts"].append(shift_schedule)
                for n in data["nurses"]:
                    nurse = n["nurse_identifier"]
                    if solver.value(shift_slots[(nurse, day, shift)]) == 1:
                        shift_schedule["nurses"].append(nurse)
        utils.print_nurse_schedule(schedule)
        if args.save:
            utils.write_nurse_schedule_to_file(
                f"schedule_{data['year']}_{data['month']}.json", schedule
            )
