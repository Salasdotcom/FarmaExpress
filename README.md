# FarmaExpress - Sistema de Gestión Farmacéutica y Arquitectura de Software
Integrantes
Colons can be used to align columns.

| Alumno      | Matricula        | 
| ------------- |:-------------:| 
| Emiliano Salas Padron     | 2157333 | 
| Jesus Adrian De la Cruz Dominguez    | 2156493  | 
| Joel Guadalupe Taméz Olmos | 2158224      | 

Profesor: Miguel Ángel Gómez Marroquín
# Alcance 

**Proceso principal** Venta en mostrador de medicamentos generales y controlados, validación de recetas médicas, gestión de inventario por lotes y caducidades , excepciones autorizadas por el Responsable de Farmacia y fiscalización sanitaria. 

* **CU-01 Registrar Venta:** Cobro en mostrador, validación de receta y emisión de ticket.
* **CU-02 Autorizar Excepción:** Aprobación trazable por el Responsable de Farmacia.
* **CU-03 Cancelar Venta:** Anulación con comprobación de caja abierta y reingreso de stock.
* **CU-04 Recall Sanitario:** Bloqueo masivo de lotes por alerta
* **CU-05 Resurtido:** Propuesta de Compras y autorización del Responsable de Farmacia.

## Estructura del repositorio


```text
FarmaExpress/
├── diagrams/
│   ├── BPMN.pdf
│   ├── Diagrama-dominio.svg
│   ├── diagrama-secuencia-1.svg
│   └── diagrama-secuencia-2.svg
├── docs/
│   ├── Equipo10-FarmaExpress-Report.doxc
│   ├── Equipo10-FarmaExpress-Report.pdf
│   ├── Matriz_FarmaExpress-3.pdf
│   └── adr.txt
├── src/
├── tests/
└── README.md
```
