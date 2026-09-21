import re
import unicodedata


class RoutingLanguageNormalizer:
    """
    Deterministic routing-only language normalization.

    The user's original text is preserved for conversation and model
    generation. This class only creates a canonical routing copy for
    deterministic safety, freshness, capability, and runtime checks.
    """

    _SPANISH_MARKERS = {
        "hola", "que", "quien", "cual", "como", "cuando", "donde",
        "puedes", "podrias", "puedo", "ahora", "hoy", "manana",
        "abre", "abrir", "cierra", "cerrar", "busca", "buscar",
        "navega", "computadora", "ordenador", "archivo", "archivos",
        "recordatorio", "recordatorios", "clima", "recuerdame",
        "explica", "fotosintesis",
    }

    _PHRASE_REPLACEMENTS = (
        ("quien te creo o desarrollo", "who created or developed you"),
        ("quien te creo", "who created you"),
        ("quien te construyo", "who built you"),
        ("quien te desarrollo", "who developed you"),
        ("quien eres", "who are you"),
        ("que eres", "what are you"),

        (
            "que modelo de ia estas usando ahora mismo",
            "what ai model are you using right now",
        ),
        (
            "que modelo de ia estas usando",
            "what ai model are you using",
        ),
        (
            "que modelo de ia usas ahora mismo",
            "what ai model are you using right now",
        ),
        (
            "que modelo de ia usas",
            "what ai model are you using",
        ),
        (
            "que modelo estas usando ahora mismo",
            "what model are you using right now",
        ),
        (
            "que proveedor estas usando ahora mismo",
            "what provider are you using right now",
        ),
        (
            "que proveedor estas usando",
            "what provider are you using",
        ),

        ("que capacidades tienes", "what capabilities do you have"),
        ("que puedes hacer", "what can you do"),
        ("puedes navegar por la web", "can you browse the web"),
        ("puedes buscar en la web", "can you search the web"),
        ("puedes usar la web", "can you use the web"),
        ("puedes usar internet", "can you use the internet"),
        (
            "puedes controlar mi computadora",
            "can you control my computer",
        ),
        (
            "puedes controlar el ordenador",
            "can you control the computer",
        ),
        (
            "puedes acceder a mis archivos",
            "can you access my files",
        ),
        ("puedes acceder a archivos", "can you access files"),
        (
            "puedes establecer recordatorios",
            "can you set reminders",
        ),
        (
            "puedes crear recordatorios",
            "can you create reminders",
        ),
        ("puedes usar herramientas", "can you use tools"),
        ("puedes ejecutar herramientas", "can you run tools"),

        ("busca en la web", "search the web"),
        ("buscar en la web", "search the web"),
        ("busca en linea", "search online"),
        ("buscar en linea", "search online"),
        ("busca en internet", "search the internet"),
        ("buscar en internet", "search the internet"),
        ("navega por la web", "browse the web"),
        ("navegar por la web", "browse the web"),
        ("mira en linea", "look online"),
        ("verifica en linea", "verify online"),
        ("verificar en linea", "verify online"),
        ("verifica en la web", "verify on the web"),
        ("usa internet", "use the internet"),

        ("como puedo", "how can i"),
        ("como hago para", "how do i"),
        ("como deberia", "how should i"),
        ("explica como", "explain how"),
        ("muestrame como", "show me how"),
        ("dime como", "tell me how"),
        ("es posible", "is it possible to"),

        ("escribe un script", "write a script"),
        ("escribe el script", "write the script"),
        ("escribe codigo", "write code"),
        ("escribe el codigo", "write the code"),
        ("genera codigo", "generate code"),
        ("genera un script", "generate a script"),

        ("recuerdame", "remind me"),
        ("establece un recordatorio", "set a reminder"),
        ("crea un recordatorio", "create a reminder"),
        ("programa un recordatorio", "schedule a reminder"),

        ("ahora mismo", "right now"),
        ("en este momento", "right now"),
        ("a partir de hoy", "as of today"),
        ("esta manana", "this morning"),
        ("esta tarde", "this afternoon"),
        ("esta noche", "tonight"),
        ("esta semana", "this week"),
        ("este fin de semana", "this weekend"),
        ("este mes", "this month"),
        ("la proxima semana", "next week"),
        ("el proximo mes", "next month"),

        ("presidente actual", "current president"),
        ("primer ministro actual", "current prime minister"),
        ("gobernador actual", "current governor"),
        ("alcalde actual", "current mayor"),
        ("ceo actual", "current ceo"),
        ("director ejecutivo actual", "current ceo"),
        ("precio actual", "current price"),
        ("clima actual", "current weather"),
        ("puntuacion actual", "current score"),
        ("estado actual", "current status"),
        ("version actual", "current version"),
        ("clasificacion actual", "current ranking"),
        ("poblacion actual", "current population"),

        ("precio de las acciones", "stock price"),
        ("precio de acciones", "stock price"),
        ("tipo de cambio", "exchange rate"),
        ("estado del vuelo", "flight status"),
        ("corte de energia", "power outage"),
        ("interrupcion del servicio", "service outage"),
        ("abierto ahora", "open now"),
    )

    _WORD_REPLACEMENTS = {
        "quien": "who",
        "que": "what",
        "cual": "which",
        "cuando": "when",
        "donde": "where",
        "como": "how",
        "puedes": "can you",
        "podrias": "could you",
        "puedo": "can i",
        "eres": "are you",
        "estas": "are you",
        "usando": "using",
        "usas": "use",
        "modelo": "model",
        "proveedor": "provider",
        "hoy": "today",
        "manana": "tomorrow",
        "ultimo": "latest",
        "ultima": "latest",
        "clima": "weather",
        "pronostico": "forecast",
        "abre": "open",
        "abrir": "open",
        "cierra": "close",
        "cerrar": "close",
        "ejecuta": "run",
        "ejecutar": "run",
        "inicia": "start",
        "iniciar": "start",
        "deten": "stop",
        "detener": "stop",
        "elimina": "delete",
        "eliminar": "delete",
        "borra": "delete",
        "borrar": "delete",
        "mueve": "move",
        "mover": "move",
        "copia": "copy",
        "copiar": "copy",
        "renombra": "rename",
        "renombrar": "rename",
        "envia": "send",
        "enviar": "send",
        "instala": "install",
        "instalar": "install",
        "sube": "upload",
        "subir": "upload",
        "descarga": "download",
        "descargar": "download",
        "crea": "create",
        "crear": "create",
        "guarda": "save",
        "guardar": "save",
        "archivo": "file",
        "archivos": "files",
        "carpeta": "folder",
        "directorio": "directory",
        "documento": "document",
        "ruta": "path",
        "recordatorio": "reminder",
        "recordatorios": "reminders",
        "herramienta": "tool",
        "herramientas": "tools",
        "explica": "explain",
        "explicar": "explain",
        "muestrame": "show me",
        "dime": "tell me",
        "busca": "search",
        "buscar": "search",
        "navega": "browse",
        "navegar": "browse",
        "verifica": "verify",
        "verificar": "verify",
        "encuentra": "find",
        "encontrar": "find",
    }

    @staticmethod
    def surface(text: str) -> str:
        value = str(text if text is not None else "")

        value = unicodedata.normalize("NFKD", value)
        value = "".join(
            ch for ch in value
            if not unicodedata.combining(ch)
        )

        value = (
            value.lower()
            .replace("¿", "")
            .replace("¡", "")
        )

        return " ".join(value.strip().split())

    @classmethod
    def language_hint(cls, text: str) -> str:
        surface = cls.surface(text)
        tokens = set(re.findall(r"[a-z0-9]+", surface))

        if (
            tokens.intersection(cls._SPANISH_MARKERS)
            or "por favor" in surface
        ):
            return "es"

        return "en"

    @staticmethod
    def _replace_phrase(
        text: str,
        source: str,
        target: str,
    ) -> str:
        pattern = (
            r"(?<!\w)"
            + re.escape(source).replace(r"\ ", r"\s+")
            + r"(?!\w)"
        )

        return re.sub(
            pattern,
            target,
            text,
            flags=re.IGNORECASE,
        )

    @classmethod
    def normalize(cls, text: str) -> str:
        value = cls.surface(text)

        if not value:
            return ""

        for source, target in sorted(
            cls._PHRASE_REPLACEMENTS,
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            value = cls._replace_phrase(
                value,
                source,
                target,
            )

        for source, target in cls._WORD_REPLACEMENTS.items():
            value = re.sub(
                r"\b" + re.escape(source) + r"\b",
                target,
                value,
                flags=re.IGNORECASE,
            )

        return " ".join(value.strip().split())
