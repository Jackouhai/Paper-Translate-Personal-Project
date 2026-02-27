import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class BaseTranslator(ABC):
    @abstractmethod
    def translate(
        self, text: str, source_lang: str = "en", target_lang: str = "vi"
    ) -> str:
        """
        Dịch text từ source_lang sang target_lang

        Returns:
            Văn bản đã dịch. Nếu lỗi, trả về text gốc
        """
        pass

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str = "en",
        target_lang: str = "vi",
    ) -> list[str | None]:
        """
        Translate multiple texts in batch.

        Default implementation calls translate() for each text.
        Override in subclasses for true batch processing.

        Returns:
            List of translations (None if failed for a particular text)
        """
        return [self.translate(text, source_lang, target_lang) for text in texts]

    async def async_translate(
        self, text: str, source_lang: str = "en", target_lang: str = "vi"
    ) -> str:
        """
        Async translate - default implementation wraps sync method.

        Override this in subclasses for true async implementation.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.translate, text, source_lang, target_lang
        )

    @classmethod
    @abstractmethod
    def load(cls, **kwargs) -> "BaseTranslator":
        """
        Factory method để khởi tạo translator
        Lazy load model khi cần
        """
        pass
