from ortools.sat.python import cp_model
from typing import List, Dict

# Példa adatok, amelyeket később kicserélhetsz a tényleges adatokra
num_nurses = 5  # Például 5 munkás, de ez dinamikusan változhat
days = 7  # Heti beosztás például
shifts_per_day = 3  # Napi műszakok száma
required_nurses_per_shift = [  # Elvárt létszám minden nap minden műszakjára
    [2, 2, 1],  # Első nap, 3 műszak
    [1, 2, 2],  # Második nap
    [2, 1, 2],  # Harmadik nap
    [2, 2, 1],  # Negyedik nap
    [1, 2, 2],  # Ötödik nap
    [2, 1, 2],  # Hatodik nap
    [1, 1, 1]   # Hetedik nap
]

# Példa szabadnap igények (minden munkás napokra megadva)
days_off_requested = {
    0: [1, 3],  # Első munkás szabadnap igényei
    1: [0, 4],  # Második munkás szabadnap igényei
    2: [2, 5],  # Harmadik munkás szabadnap igényei
    3: [3, 6],  # Negyedik munkás szabadnap igényei
    4: [1, 5]   # Ötödik munkás szabadnap igényei
}

# Model inicializálása
model = cp_model.CpModel()

# Változók inicializálása: shift_slots jelzi, hogy egy adott munkás dolgozik-e egy adott napon egy adott műszakban
shift_slots: Dict[tuple, cp_model.IntVar] = {}
for nurse in range(num_nurses):
    for day in range(days):
        for shift in range(shifts_per_day):
            shift_slots[(nurse, day, shift)] = model.NewBoolVar(f'shift_n{nurse}_d{day}_s{shift}')

# Constraint: Egy munkás legfeljebb egy műszakban dolgozhat naponta
for nurse in range(num_nurses):
    for day in range(days):
        model.AddAtMostOne(shift_slots[(nurse, day, shift)] for shift in range(shifts_per_day))

# Constraint: A munkás nem dolgozhat, ha szabadnapot kért
for nurse, days_off in days_off_requested.items():
    for day in days_off:
        for shift in range(shifts_per_day):
            model.Add(shift_slots[(nurse, day, shift)] == 0)

# Constraint: Minden műszaknak meg kell felelnie az elvárt létszámnak
for day in range(days):
    for shift in range(shifts_per_day):
        model.Add(sum(shift_slots[(nurse, day, shift)] for nurse in range(num_nurses)) == required_nurses_per_shift[day][shift])

# Változók az egyenletes munkamegosztáshoz
shift_counts = []
shift_counts_squared = []
for nurse in range(num_nurses):
    count_var = model.NewIntVar(0, days * shifts_per_day, f'nurse_{nurse}_shift_count')
    count_var_squared = model.NewIntVar(0, (days * shifts_per_day) ** 2, f'nurse_{nurse}_shift_count_squared')
    shift_counts.append(count_var)
    shift_counts_squared.append(count_var_squared)
    
    # Munkás által teljesített műszakok száma
    model.Add(count_var == sum(shift_slots[(nurse, day, shift)] for day in range(days) for shift in range(shifts_per_day)))
    # Munkás által teljesített műszakok számának négyzete
    model.AddMultiplicationEquality(count_var_squared, [count_var, count_var])

# Célfüggvény: minimalizálja a műszakok számának négyzetösszegét az egyenletes elosztás érdekében
model.Minimize(sum(shift_counts_squared))

# Megoldó inicializálása és megoldás keresése
solver = cp_model.CpSolver()
status = solver.Solve(model)

# Eredmények kiírása
if status == cp_model.OPTIMAL:
    print('Optimális megoldás találva:')
    schedule = [[[] for _ in range(shifts_per_day)] for _ in range(days)]
    for day in range(days):
        for shift in range(shifts_per_day):
            working_nurses = []
            for nurse in range(num_nurses):
                if solver.Value(shift_slots[(nurse, day, shift)]) == 1:
                    working_nurses.append(nurse)
            schedule[day][shift] = working_nurses

    # Táblázat formátumú kimenet
    for day in range(days):
        print(f'Nap {day + 1}:')
        for shift in range(shifts_per_day):
            print(f'  Műszak {shift + 1}: {schedule[day][shift]}')
else:
    print('Nem található optimális megoldás.')

