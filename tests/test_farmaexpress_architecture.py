
import unittest
from datetime import date, timedelta

from farmaexpress_architecture import (
    Lote,
    ExistenciaDeProducto,
    Receta,
    InMemoryVentaRepository,
    InMemoryExistenciaRepository,
    InMemoryUnitOfWork,
    VentaApplicationService,
    RegistrarVentaCommand,
    DomainException
)


class TestFarmaExpressArchitecture(unittest.TestCase):

    def setUp(self):
        self.hoy = date(2026, 10, 16)

        self.venta_repo = InMemoryVentaRepository()
        self.existencia_repo = InMemoryExistenciaRepository()
        self.uow = InMemoryUnitOfWork()

        self.service = VentaApplicationService(
            self.venta_repo,
            self.existencia_repo,
            self.uow
        )

        # Cargar inventario inicial en la sucursal.
        lote_valido = Lote(
            numero_lote="LOTE-001",
            fecha_caducidad=date(2027, 5, 1),
            cantidad=50
        )

        lote_vencido = Lote(
            numero_lote="LOTE-VENCIDO",
            fecha_caducidad=date(2026, 1, 1),
            cantidad=20
        )

        existencia = ExistenciaDeProducto(
            id_existencia="EX-001",
            producto_id="P100",
            sucursal_id="S001",
            lotes=[lote_valido, lote_vencido]
        )

        self.existencia_repo.guardar(existencia)

    def test_01_venta_exitosa_medicamento_controlado_con_receta_valida(self):
        receta_valida = Receta(
            folio="REC-8899",
            medico="Dr. Carlos Gómez",
            cedula_medico="CED-12345",
            nombre_paciente="Juan Pérez",
            fecha_emision=self.hoy - timedelta(days=5)
        )

        cmd = RegistrarVentaCommand(
            id_venta="V-101",
            folio_ticket="TICK-001",
            sucursal_id="S001",
            cajero_id="CAJ-01",
            producto_id="P100",
            numero_lote="LOTE-001",
            cantidad=5,
            precio_unitario=150.0,
            es_controlado=True,
            receta=receta_valida
        )

        evento = self.service.registrar_venta(
            cmd,
            fecha_actual=self.hoy
        )

        self.assertEqual(evento.folio_ticket, "TICK-001")
        self.assertEqual(evento.total, 750.0)
        self.assertTrue(self.uow.committed)

        # Validar descuento de stock.
        ex = self.existencia_repo.obtener_por_producto_y_sucursal(
            "P100",
            "S001"
        )

        lote = next(
            l for l in ex.lotes
            if l.numero_lote == "LOTE-001"
        )

        self.assertEqual(lote.cantidad, 45)  # 50 - 5 = 45

    def test_02_rechazo_venta_controlado_sin_receta_y_rollback(self):
        cmd = RegistrarVentaCommand(
            id_venta="V-102",
            folio_ticket="TICK-002",
            sucursal_id="S001",
            cajero_id="CAJ-01",
            producto_id="P100",
            numero_lote="LOTE-001",
            cantidad=2,
            precio_unitario=150.0,
            es_controlado=True,
            receta=None
        )

        with self.assertRaises(DomainException) as ctx:
            self.service.registrar_venta(
                cmd,
                fecha_actual=self.hoy
            )

        self.assertIn(
            "Medicamento controlado exige receta médica",
            str(ctx.exception)
        )

        self.assertTrue(self.uow.rolled_back)
        self.assertFalse(self.uow.committed)

        # Validar que el inventario se mantuvo intacto.
        ex = self.existencia_repo.obtener_por_producto_y_sucursal(
            "P100",
            "S001"
        )

        lote = next(
            l for l in ex.lotes
            if l.numero_lote == "LOTE-001"
        )

        self.assertEqual(lote.cantidad, 50)

    def test_03_intento_venta_lote_vencido(self):
        receta = Receta(
            "REC-8899",
            "Dr. Gómez",
            "CED-12345",
            "Juan Pérez",
            self.hoy
        )

        cmd = RegistrarVentaCommand(
            "V-103",
            "TICK-003",
            "S001",
            "CAJ-01",
            "P100",
            "LOTE-VENCIDO",
            1,
            150.0,
            True,
            receta
        )

        with self.assertRaises(DomainException) as ctx:
            self.service.registrar_venta(
                cmd,
                fecha_actual=self.hoy
            )

        self.assertIn(
            "bloqueado o vencido",
            str(ctx.exception)
        )

        self.assertTrue(self.uow.rolled_back)

    def test_04_bloqueo_de_lote_por_recall_sanitario(self):
        ex = self.existencia_repo.obtener_por_producto_y_sucursal(
            "P100",
            "S001"
        )

        ex.bloquear_lote_por_recall(
            "LOTE-001",
            "Alerta sanitaria COFEPRIS"
        )

        receta = Receta(
            "REC-1111",
            "Dr. López",
            "CED-999",
            "Pedro",
            self.hoy
        )

        cmd = RegistrarVentaCommand(
            "V-104",
            "TICK-004",
            "S001",
            "CAJ-01",
            "P100",
            "LOTE-001",
            1,
            150.0,
            True,
            receta
        )

        with self.assertRaises(DomainException) as ctx:
            self.service.registrar_venta(
                cmd,
                fecha_actual=self.hoy
            )

        self.assertIn(
            "bloqueado o vencido",
            str(ctx.exception)
        )


if __name__ == '__main__':
    unittest.main()
