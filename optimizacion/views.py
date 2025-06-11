from django.shortcuts import render

import json
from django.http import JsonResponse
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpBinary, value
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def asignacion_optima(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": "JSON inválido", "detalle": str(e)}, status=400)
    
    delta = data.get("delta", 1.0)
    lambda_penal = data.get("lambda_penal", 1.0)
    grupos = data["grupos"]
    aulas = data["aulas"]
    horarios = data["horarios"]

    # Identificadores
    G = list(range(len(grupos)))
    A = list(range(len(aulas)))
    H = list(range(len(horarios)))

    # Construir el problema
    prob = LpProblem("Asignacion_Grupos_Aulas_Horarios", LpMinimize)

    # Variables: x[g][a][h] = 1 si grupo g está en aula a en horario h
    x = [[[LpVariable(f"x_{g}_{a}_{h}", cat=LpBinary) for h in H] for a in A] for g in G]
    # Variables: y[g] = 1 si grupo g NO es asignado
    y = [LpVariable(f"y_{g}", cat=LpBinary) for g in G]

    # Objetivo: minimizar penalizaciones
    # Penaliza grupos no asignados y también asignaciones a aulas con capacidad insuficiente
    penalizaciones = []
    for g in G:
        for a in A:
            for h in H:
                overcap = max(0, grupos[g]["estudiantes"] - aulas[a]["capacidad"])
                penal = lambda_penal * overcap  # penalización por exceso de estudiantes
                penalizaciones.append(x[g][a][h] * penal)
        penalizaciones.append(y[g] * delta)  # penalización por grupo no asignado

    prob += lpSum(penalizaciones), "Penalizacion_Total"

    # Restricción 1: Cada grupo solo se asigna a un aula y horario (o no es asignado)
    for g in G:
        prob += lpSum([x[g][a][h] for a in A for h in H]) + y[g] == 1

    # Restricción 2: No más de un grupo en cada aula y horario
    for a in A:
        for h in H:
            prob += lpSum([x[g][a][h] for g in G]) <= 1

    # (opcional) Solo permitir asignar grupos a aulas con capacidad al menos 80% del tamaño del grupo
    # for g in G:
    #     for a in A:
    #         if aulas[a]["capacidad"] < grupos[g]["estudiantes"] * 0.8:
    #             for h in H:
    #                 prob += x[g][a][h] == 0

    # Resolver
    prob.solve()

    # Extraer soluciones
    asignaciones = []
    for g in G:
        asignado = False
        for a in A:
            for h in H:
                if value(x[g][a][h]) == 1:
                    asignado = True
                    aula = aulas[a]
                    horario = horarios[h]
                    overcap = grupos[g]["estudiantes"] - aula["capacidad"]
                    asignaciones.append({
                        "grupo": grupos[g]["nombre"],
                        "materia": grupos[g]["materia"],
                        "estudiantes": grupos[g]["estudiantes"],
                        "aula": aula["nombre"],
                        "capacidad_aula": aula["capacidad"],
                        "horario": horario["bloque"],
                        "penalizacion": max(0, overcap) * lambda_penal,
                        "observacion": ("¡Exceso de estudiantes en aula!" if overcap > 0 else "")
                    })
        if not asignado:
            asignaciones.append({
                "grupo": grupos[g]["nombre"],
                "materia": grupos[g]["materia"],
                "estudiantes": grupos[g]["estudiantes"],
                "aula": None,
                "capacidad_aula": None,
                "horario": None,
                "penalizacion": delta,
                "observacion": "Grupo no asignado"
            })

    resultado = {
        "asignaciones": asignaciones,
        "penalizacion_total": float(value(prob.objective))
    }
    return JsonResponse(resultado, safe=False)
