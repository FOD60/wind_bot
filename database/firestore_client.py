"""
Асинхронная обёртка над синхронным Firestore-клиентом.
Все I/O-вызовы выполняются через asyncio.to_thread(),
чтобы не блокировать event loop aiogram.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from database.firebase_init import get_db

logger = logging.getLogger(__name__)


class AsyncFirestore:
    """Async-обёртка: каждый метод оборачивает синхронный вызов Firestore."""

    # ─────────── Документы ───────────

    @staticmethod
    async def get_doc(collection: str, doc_id: str) -> Optional[dict]:
        """Получить документ. Вернёт dict или None."""
        db = get_db()

        def _get():
            doc = db.collection(collection).document(str(doc_id)).get()
            if doc.exists:
                data = doc.to_dict()
                data["_id"] = doc.id
                return data
            return None

        return await asyncio.to_thread(_get)

    @staticmethod
    async def set_doc(
        collection: str,
        doc_id: str,
        data: dict,
        merge: bool = False,
    ) -> None:
        """Создать/перезаписать документ."""
        db = get_db()
        await asyncio.to_thread(
            db.collection(collection).document(str(doc_id)).set,
            data,
            merge,
        )

    @staticmethod
    async def update_doc(collection: str, doc_id: str, data: dict) -> None:
        """Обновить поля документа (частичное обновление)."""
        db = get_db()
        await asyncio.to_thread(
            db.collection(collection).document(str(doc_id)).update,
            data,
        )

    @staticmethod
    async def delete_doc(collection: str, doc_id: str) -> None:
        """Удалить документ."""
        db = get_db()
        await asyncio.to_thread(
            db.collection(collection).document(str(doc_id)).delete,
        )

    @staticmethod
    async def add_doc(collection: str, data: dict) -> str:
        """Добавить документ с автогенерацией ID. Возвращает ID."""
        db = get_db()

        def _add():
            _, ref = db.collection(collection).add(data)
            return ref.id

        return await asyncio.to_thread(_add)

    # ─────────── Запросы ───────────

    @staticmethod
    async def query(
        collection: str,
        filters: list[tuple[str, str, Any]] | None = None,
        order_by: str | None = None,
        direction: str = "ASCENDING",
        limit: int | None = None,
    ) -> list[tuple[str, dict]]:
        """
        Запрос к коллекции.

        Args:
            collection: имя коллекции
            filters: список кортежей (field, op, value),
                     например [("level", ">=", 5), ("is_vip", "==", True)]
            order_by: поле для сортировки
            direction: "ASCENDING" или "DESCENDING"
            limit: максимум документов

        Returns:
            Список кортежей (doc_id, doc_dict).
        """
        db = get_db()

        def _execute():
            ref = db.collection(collection)

            if filters:
                for field_path, op_string, value in filters:
                    ref = ref.where(field_path, op_string, value)

            if order_by:
                from google.cloud.firestore_v1 import Query

                dir_val = (
                    Query.DESCENDING
                    if direction == "DESCENDING"
                    else Query.ASCENDING
                )
                ref = ref.order_by(order_by, direction=dir_val)

            if limit:
                ref = ref.limit(limit)

            return [(doc.id, doc.to_dict()) for doc in ref.stream()]

        return await asyncio.to_thread(_execute)

    # ─────────── Пакетные операции ───────────

    @staticmethod
    async def batch_update(
        collection: str,
        updates: list[tuple[str, dict]],
    ) -> int:
        """
        Пакетное обновление документов.

        Args:
            collection: имя коллекции
            updates: список кортежей (doc_id, update_data)

        Returns:
            Количество обновлённых документов.
        """
        db = get_db()

        def _batch():
            batch = db.batch()
            count = 0
            for i, (doc_id, data) in enumerate(updates):
                ref = db.collection(collection).document(str(doc_id))
                batch.update(ref, data)
                count += 1
                if (i + 1) % 500 == 0:
                    batch.commit()
                    batch = db.batch()
            if count % 500 != 0:
                batch.commit()
            return count

        return await asyncio.to_thread(_batch)

    # ─────────── Транзакции ───────────

    @staticmethod
    async def run_transaction(callback):
        """
        Выполнить Firestore-транзакцию.

        callback(transaction, db) — синхронная функция:
          - чтение:  ref.get(transaction=transaction)
          - запись:   transaction.update(ref, data)
                      transaction.set(ref, data)

        Пример:
            def transfer(transaction, db):
                s_ref = db.collection("users").document("123")
                r_ref = db.collection("users").document("456")
                s = s_ref.get(transaction=transaction).to_dict()
                r = r_ref.get(transaction=transaction).to_dict()
                transaction.update(s_ref, {"winds_balance": s["winds_balance"] - 100})
                transaction.update(r_ref, {"winds_balance": r["winds_balance"] + 100})

            await db_client.run_transaction(transfer)
        """
        from google.cloud.firestore_v1.transaction import transactional

        db = get_db()

        @transactional
        def _run(transaction):
            return callback(transaction, db)

        return await asyncio.to_thread(_run, db.transaction())

    # ─────────── Атомарный инкремент ───────────

    @staticmethod
    async def increment_field(
        collection: str,
        doc_id: str,
        field: str,
        value: int,
    ) -> None:
        """
        Атомарно увеличить числовое поле на value.
        Отрицательный value — уменьшение.
        """
        from google.cloud.firestore_v1 import Increment

        db = get_db()
        await asyncio.to_thread(
            db.collection(collection).document(str(doc_id)).update,
            {field: Increment(value)},
        )


# Глобальный экземпляр — импортируйте его:
#   from database.firestore_client import db_client
db_client = AsyncFirestore()
