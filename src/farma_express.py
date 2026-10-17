
import dataclasses
from datetime import datetime, date
from typing import List, Optional, Dict
from abc import ABC, abstractmethod


# ==========================================
# 1. DOMAIN LAYER
# Value Objects, Entities, Aggregates, Events
# ==========================================

class DomainException(Exception):
    """Excepción base para violaciones de reglas de negocio e invariantes."""
    pass


@dataclasses.dataclass(frozen=True)
class Receta:
    """Value Object inmutable que representa una receta médica."""

    folio: str
    medico: str
    cedula_medico: str
    nombre_paciente: str
    fecha_emision: date

    def es_vigente(
        self,
        fecha_actual: date,
        dias_max_vigencia: int = 30
    ) -> bool:
        delta = (fecha_actual - self.fecha_emision).days
        return 0 <= delta <= dias_max_vigencia


@dataclasses.dataclass(frozen=True)
class AutorizacionDeExcepcion:
    """Value Object inmutable para excepciones del Responsable de Farmacia."""

    id_gerente: str
    motivo: str
    timestamp: datetime


class DomainEvent:
    """Clase base para eventos de negocio."""
    pass


@dataclasses.dataclass(frozen=True)
class VentaRegistrada(DomainEvent):
    id_venta: str
    folio_ticket: str
    total: float
    timestamp: datetime


@dataclasses.dataclass(frozen=True)
class LoteBloqueado(DomainEvent):
    numero_lote: str
    motivo: str


class Lote:
    """Entidad Lote dentro del Agregado ExistenciaDeProducto."""

    def __init__(
        self,
        numero_lote: str,
        fecha_caducidad: date,
        cantidad: int,
        bloqueado: bool = False
    ):
        self.numero_lote = numero_lote
        self.fecha_caducidad = fecha_caducidad
        self.cantidad = cantidad
        self.bloqueado = bloqueado

    def esta_disponible_para_venta(self, fecha_actual: date) -> bool:
        return (
            not self.bloqueado
            and self.fecha_caducidad > fecha_actual
        )

    def descontar(self, cantidad: int, fecha_actual: date):
        if not self.esta_disponible_para_venta(fecha_actual):
            raise DomainException(
                f"El lote {self.numero_lote} está bloqueado o vencido."
            )

        if cantidad > self.cantidad:
            raise DomainException(
                f"Stock insuficiente en lote {self.numero_lote}. "
                f"Disponible: {self.cantidad}, Solicitado: {cantidad}"
            )

        self.cantidad -= cantidad


class ExistenciaDeProducto:
    """Aggregate Root que controla el inventario por producto y sucursal."""

    def __init__(
        self,
        id_existencia: str,
        producto_id: str,
        sucursal_id: str,
        lotes: List[Lote]
    ):
        self.id_existencia = id_existencia
        self.producto_id = producto_id
        self.sucursal_id = sucursal_id
        self.lotes = lotes

    def descontar_stock(
        self,
        numero_lote: str,
        cantidad: int,
        fecha_actual: date
    ):
        lote = next(
            (l for l in self.lotes if l.numero_lote == numero_lote),
            None
        )

        if not lote:
            raise DomainException(
                f"No se encontró el lote {numero_lote} "
                f"en la sucursal {self.sucursal_id}."
            )

        lote.descontar(cantidad, fecha_actual)

    def bloquear_lote_por_recall(
        self,
        numero_lote: str,
        motivo: str
    ) -> LoteBloqueado:
        lote = next(
            (l for l in self.lotes if l.numero_lote == numero_lote),
            None
        )

        if not lote:
            raise DomainException(
                f"Lote {numero_lote} no encontrado para recall."
            )

        lote.bloqueado = True

        return LoteBloqueado(
            numero_lote=numero_lote,
            motivo=motivo
        )


class DetalleVenta:
    """Entidad de línea de detalle de la venta."""

    def __init__(
        self,
        producto_id: str,
        numero_lote: str,
        cantidad: int,
        precio_unitario: float,
        es_controlado: bool
    ):
        self.producto_id = producto_id
        self.numero_lote = numero_lote
        self.cantidad = cantidad
        self.precio_unitario = precio_unitario
        self.es_controlado = es_controlado

    @property
    def subtotal(self) -> float:
        return self.cantidad * self.precio_unitario


class Venta:
    """Aggregate Root de Venta en Mostrador."""

    def __init__(
        self,
        id_venta: str,
        folio_ticket: str,
        sucursal_id: str,
        cajero_id: str
    ):
        self.id_venta = id_venta
        self.folio_ticket = folio_ticket
        self.sucursal_id = sucursal_id
        self.cajero_id = cajero_id

        self.detalles: List[DetalleVenta] = []
        self.receta: Optional[Receta] = None
        self.excepcion: Optional[AutorizacionDeExcepcion] = None
        self.estado: str = "REGISTRADA"
        self.eventos: List[DomainEvent] = []

    @property
    def total(self) -> float:
        return sum(d.subtotal for d in self.detalles)

    def agregar_detalle(
        self,
        producto_id: str,
        numero_lote: str,
        cantidad: int,
        precio: float,
        es_controlado: bool
    ):
        if cantidad <= 0:
            raise DomainException(
                "La cantidad debe ser mayor a cero."
            )

        self.detalles.append(
            DetalleVenta(
                producto_id,
                numero_lote,
                cantidad,
                precio,
                es_controlado
            )
        )

    def asociar_receta(self, receta: Receta, fecha_actual: date):
        if not receta.es_vigente(fecha_actual):
            raise DomainException(
                f"La receta folio {receta.folio} está vencida o es inválida."
            )

        self.receta = receta

    def confirmar_venta(self) -> VentaRegistrada:
        # Invariante: un medicamento controlado exige receta médica
        # válida o autorización de excepción.
        tiene_controlados = any(
            d.es_controlado for d in self.detalles
        )

        if tiene_controlados and not self.receta and not self.excepcion:
            raise DomainException(
                "No se puede completar la venta: "
                "Medicamento controlado exige receta médica válida "
                "o autorización de excepción."
            )

        evento = VentaRegistrada(
            id_venta=self.id_venta,
            folio_ticket=self.folio_ticket,
            total=self.total,
            timestamp=datetime.now()
        )

        self.eventos.append(evento)
        return evento


# ==========================================
# 2. REPOSITORY & UNIT OF WORK INTERFACES
# ==========================================

class IVentaRepository(ABC):

    @abstractmethod
    def agregar(self, venta: Venta):
        pass


class IExistenciaRepository(ABC):

    @abstractmethod
    def obtener_por_producto_y_sucursal(
        self,
        producto_id: str,
        sucursal_id: str
    ) -> Optional[ExistenciaDeProducto]:
        pass

    @abstractmethod
    def guardar(self, existencia: ExistenciaDeProducto):
        pass


class IUnitOfWork(ABC):

    @abstractmethod
    def begin(self):
        pass

    @abstractmethod
    def commit(self):
        pass

    @abstractmethod
    def rollback(self):
        pass


# ==========================================
# 3. INFRASTRUCTURE LAYER
# In-Memory Implementations
# ==========================================

class InMemoryVentaRepository(IVentaRepository):

    def __init__(self):
        self._ventas: Dict[str, Venta] = {}

    def agregar(self, venta: Venta):
        self._ventas[venta.id_venta] = venta


class InMemoryExistenciaRepository(IExistenciaRepository):

    def __init__(self):
        self._existencias: Dict[str, ExistenciaDeProducto] = {}

    def guardar(self, existencia: ExistenciaDeProducto):
        key = f"{existencia.sucursal_id}_{existencia.producto_id}"
        self._existencias[key] = existencia

    def obtener_por_producto_y_sucursal(
        self,
        producto_id: str,
        sucursal_id: str
    ) -> Optional[ExistenciaDeProducto]:
        key = f"{sucursal_id}_{producto_id}"
        return self._existencias.get(key)


class InMemoryUnitOfWork(IUnitOfWork):

    def __init__(self):
        self.in_transaction = False
        self.committed = False
        self.rolled_back = False

    def begin(self):
        self.in_transaction = True
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True
        self.in_transaction = False

    def rollback(self):
        self.rolled_back = True
        self.in_transaction = False


# ==========================================
# 4. APPLICATION SERVICE / ORQUESTRADOR
# ==========================================

@dataclasses.dataclass
class RegistrarVentaCommand:
    id_venta: str
    folio_ticket: str
    sucursal_id: str
    cajero_id: str
    producto_id: str
    numero_lote: str
    cantidad: int
    precio_unitario: float
    es_controlado: bool
    receta: Optional[Receta] = None


class VentaApplicationService:

    def __init__(
        self,
        venta_repo: IVentaRepository,
        existencia_repo: IExistenciaRepository,
        uow: IUnitOfWork
    ):
        self.venta_repo = venta_repo
        self.existencia_repo = existencia_repo
        self.uow = uow

    def registrar_venta(
        self,
        cmd: RegistrarVentaCommand,
        fecha_actual: date
    ) -> VentaRegistrada:
        self.uow.begin()

        try:
            existencia = (
                self.existencia_repo.obtener_por_producto_y_sucursal(
                    cmd.producto_id,
                    cmd.sucursal_id
                )
            )

            if not existencia:
                raise DomainException(
                    "Producto no disponible en la sucursal."
                )

            venta = Venta(
                cmd.id_venta,
                cmd.folio_ticket,
                cmd.sucursal_id,
                cmd.cajero_id
            )

            venta.agregar_detalle(
                cmd.producto_id,
                cmd.numero_lote,
                cmd.cantidad,
                cmd.precio_unitario,
                cmd.es_controlado
            )

            if cmd.receta:
                venta.asociar_receta(
                    cmd.receta,
                    fecha_actual
                )

            # Validar reglas e invariantes del dominio.
            evento = venta.confirmar_venta()

            # Modificar inventario.
            existencia.descontar_stock(
                cmd.numero_lote,
                cmd.cantidad,
                fecha_actual
            )

            # Guardar mediante repositorios.
            self.venta_repo.agregar(venta)
            self.existencia_repo.guardar(existencia)

            # Commit de la transacción.
            self.uow.commit()

            return evento

        except Exception:
            self.uow.rollback()
            raise
