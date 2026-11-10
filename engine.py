import json
import os
import random
import sys

# Folderul în care se află engine.py – fișierele JSON se caută aici,
# indiferent din ce folder rulezi comanda.
FOLDER = os.path.dirname(os.path.abspath(__file__))

# Pozițiile vecinilor față de celula (i, j)
VECINI = {
    "moore":       [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)],
    "von_neumann": [(-1, 0), (1, 0), (0, -1), (0, 1)],
}

# Toate automatele stau în folderul "automate", câte un fișier JSON fiecare
# (lumea + regulile în același fișier). Tipurile posibile:
#   "vecini"  – celula se schimbă după vecini (Brian's Brain, Forest Fire...)
#   "miscare" – celule care se mișcă (Predator-Prey, Ecosystem...)
#   "numere"  – celule cu cifre (Sandpile, Difuzie...)
FOLDER_AUTOMATE = os.path.join(FOLDER, "automate")


def alege_automat():
    """Afișează automatele din folder; utilizatorul scrie numărul sau numele."""
    fisiere = sorted(f for f in os.listdir(FOLDER_AUTOMATE) if f.endswith(".json"))
    for k, f in enumerate(fisiere, 1):
        print(f"{k}. {f[:-5]}")
    alegere = input("\nScrie numarul sau numele automatului: ").strip()
    if alegere.isdigit() and 1 <= int(alegere) <= len(fisiere):
        return os.path.join(FOLDER_AUTOMATE, fisiere[int(alegere) - 1])
    if alegere + ".json" in fisiere:
        return os.path.join(FOLDER_AUTOMATE, alegere + ".json")
    sys.exit(f"Eroare: nu exista automatul '{alegere}'.")


def citeste_json(fisier):
    if not os.path.isabs(fisier) and not os.path.exists(fisier):
        fisier = os.path.join(FOLDER, fisier)
    with open(fisier, "r", encoding="utf-8") as f:
        return json.load(f)


def citeste_matrice(automat):
    if automat["tip"] == "numere":
        # "0 1 2" -> [0, 1, 2]
        return [[float(x) if "." in x else int(x) for x in linie.split()] for linie in automat["matrice"]]

    simbol_la_stare = {simbol: stare for stare, simbol in automat["stari"].items()}
    matrice = []
    for linie in automat["matrice"]:
        rand = []
        for simbol in linie:
            if simbol not in simbol_la_stare:
                sys.exit(f"Eroare: simbolul '{simbol}' din matrice nu este definit în 'stari'.")
            rand.append(simbol_la_stare[simbol])
        matrice.append(rand)
    return matrice


def in_matrice(matrice, i, j):
    return 0 <= i < len(matrice) and 0 <= j < len(matrice[0])


def vecinii(matrice, i, j, directii):
    """Lista pozițiilor vecinilor care sunt în interiorul matricei."""
    return [(i + di, j + dj) for di, dj in directii if in_matrice(matrice, i + di, j + dj)]


# =====================================================================
# TIP 1: "vecini" – celula își schimbă starea după câți vecini are
# =====================================================================

def compara(a, semn, b):
    if semn == "==": return a == b
    if semn == "!=": return a != b
    if semn == ">=": return a >= b
    if semn == "<=": return a <= b
    if semn == ">":  return a > b
    if semn == "<":  return a < b
    sys.exit(f"Eroare: semn necunoscut '{semn}'.")


def numara_vecini(matrice, i, j, stare, directii):
    return sum(1 for vi, vj in vecinii(matrice, i, j, directii) if matrice[vi][vj] == stare)


def pas_vecini(matrice, reguli, directii, date):
    noua = [rand[:] for rand in matrice]
    for i in range(len(matrice)):
        for j in range(len(matrice[0])):
            for r in reguli["reguli"]:
                if matrice[i][j] != r["din"]:
                    continue
                if "daca" in r:
                    nr = numara_vecini(matrice, i, j, r["daca"], directii)
                    prag = r["nr"]
                    if isinstance(prag, str):      # "nr": "A" -> comparăm cu numărul de vecini A
                        prag = numara_vecini(matrice, i, j, prag, directii)
                    if not compara(nr, r["semn"], prag):
                        continue
                noua[i][j] = r["in"]
                break                              # se aplică doar prima regulă potrivită
    return noua


# =====================================================================
# TIP 2: "miscare" – agenți care se mută, mănâncă, se înmulțesc, mor
# =====================================================================

def pregateste_miscare(matrice, reguli):
    """Fiecare agent primește energie și vârstă (ținute în matrici separate)."""
    energie = [[0] * len(matrice[0]) for _ in matrice]
    varsta = [[0] * len(matrice[0]) for _ in matrice]
    for i in range(len(matrice)):
        for j in range(len(matrice[0])):
            agent = reguli["agenti"].get(matrice[i][j])
            if agent and agent.get("energie_start") is not None:
                energie[i][j] = agent["energie_start"]
    return {"energie": energie, "varsta": varsta}


def muta(matrice, date, din, spre, gol):
    (i, j), (a, b) = din, spre
    matrice[a][b] = matrice[i][j]
    date["energie"][a][b] = date["energie"][i][j]
    date["varsta"][a][b] = date["varsta"][i][j]
    matrice[i][j] = gol
    date["energie"][i][j] = 0
    date["varsta"][i][j] = 0


def pas_miscare(matrice, reguli, directii, date):
    matrice = [rand[:] for rand in matrice]
    gol = reguli["gol"]
    energie, varsta = date["energie"], date["varsta"]

    # agenții se mișcă pe rând, în ordine aleatoare
    pozitii = [(i, j) for i in range(len(matrice)) for j in range(len(matrice[0]))
               if matrice[i][j] in reguli["agenti"]]
    random.shuffle(pozitii)
    mutati = set()

    for (i, j) in pozitii:
        if (i, j) in mutati or matrice[i][j] not in reguli["agenti"]:
            continue                               # a fost deja mutat sau mâncat
        agent = reguli["agenti"][matrice[i][j]]
        varsta[i][j] += 1
        vecini = vecinii(matrice, i, j, directii)

        # 1. dacă are mâncare lângă el, merge acolo și mănâncă
        hrana = [p for p in vecini if agent.get("mananca") and matrice[p[0]][p[1]] == agent["mananca"]]
        libere = [p for p in vecini if matrice[p[0]][p[1]] == gol]
        if hrana:
            tinta = random.choice(hrana)
            energie[i][j] += agent.get("energie_castig", 0)
        else:
            # 2. altfel se mută aleator într-o celulă liberă și pierde energie
            tinta = random.choice(libere) if libere else None
            if agent.get("energie_start") is not None:
                energie[i][j] -= agent.get("energie_cost", 1)
                if energie[i][j] <= 0:             # 3. moare dacă nu mai are energie
                    matrice[i][j] = gol
                    energie[i][j] = varsta[i][j] = 0
                    continue

        if tinta is None:
            continue
        tip_agent = matrice[i][j]
        muta(matrice, date, (i, j), tinta, gol)
        mutati.add(tinta)

        # 4. înmulțire: după N pași lasă un pui în locul de unde a plecat
        n = agent.get("inmultire_dupa", 0)
        if n and varsta[tinta[0]][tinta[1]] >= n:
            varsta[tinta[0]][tinta[1]] = 0
            matrice[i][j] = tip_agent
            if agent.get("energie_start") is not None:
                energie[i][j] = agent["energie_start"]
            mutati.add((i, j))
    return matrice


# =====================================================================
# TIP 3: "numere" – celule cu cifre, noua valoare se calculează cu o formulă
#   x       = valoarea celulei
#   vecini  = lista valorilor vecinilor
# =====================================================================

def pas_numere(matrice, reguli, directii, date):
    noua = []
    for i in range(len(matrice)):
        rand = []
        for j in range(len(matrice[0])):
            valori_vecini = [matrice[a][b] for a, b in vecinii(matrice, i, j, directii)]
            variabile = {"x": matrice[i][j], "vecini": valori_vecini,
                         "sum": sum, "len": len, "min": min, "max": max, "round": round}
            valoare = eval(reguli["formula"], {"__builtins__": {}, **variabile})
            rand.append(round(valoare, 2) if isinstance(valoare, float) else int(valoare))
        noua.append(rand)
    return noua


PASI = {"vecini": pas_vecini, "miscare": pas_miscare, "numere": pas_numere}


# =====================================================================
# Afișare, rulare, răspunsuri
# =====================================================================

def afiseaza(matrice, automat):
    for rand in matrice:
        if automat["tip"] == "numere":
            print(" ".join(str(v) for v in rand))
        else:
            print(" ".join(automat["stari"][stare] for stare in rand))


def main():
    fisier = sys.argv[1] if len(sys.argv) > 1 else alege_automat()
    automat = citeste_json(fisier)

    tip = automat["tip"]
    if tip not in PASI:
        sys.exit(f"Eroare: tipul '{tip}' nu există. Tipuri valide: {list(PASI)}")
    reguli = automat                  # regulile sunt în același fișier cu lumea

    random.seed(automat.get("seed"))
    matrice = citeste_matrice(automat)
    directii = VECINI[automat.get("vecini", "moore")]
    date = pregateste_miscare(matrice, reguli) if tip == "miscare" else None
    pas = PASI[tip]
    n = automat.get("generatii", 10)

    print(f"=== {automat['nume']} (tip: {tip}) ===")
    istoric = [matrice]
    print("\nGeneratia 0:")
    afiseaza(matrice, automat)
    for g in range(1, n + 1):
        matrice = pas(matrice, reguli, directii, date)
        istoric.append(matrice)
        print(f"\nGeneratia {g}:")
        afiseaza(matrice, automat)

    print("\n--- Raspunsuri ---")
    print(f"1. Starea dupa {n} iteratii este cea de la Generatia {n}.")

    stabil = next((g - 1 for g in range(1, len(istoric)) if istoric[g] == istoric[g - 1]), None)
    print(f"2. Stare stabila de la generatia {stabil}." if stabil is not None
          else f"2. Nu s-a stabilizat in {n} generatii.")

    if "numara" in automat:
        x = automat["numara"]
        print(f"4. Celule {x} dupa {n} iteratii: {sum(rand.count(x) for rand in matrice)}")

    ciclu = None
    for g in range(len(istoric)):
        for anterior in range(g):
            if istoric[g] == istoric[anterior]:
                ciclu = (anterior, g - anterior)
                break
        if ciclu:
            break
    if ciclu and ciclu[1] > 1:
        print(f"5. Ciclu: generatia {ciclu[0]} se repeta la fiecare {ciclu[1]} pasi.")
    elif ciclu:
        print("5. Nu e ciclu propriu-zis: sistemul s-a oprit (stare stabila).")
    else:
        print(f"5. Niciun ciclu in {n} generatii.")


if __name__ == "__main__":
    main()
