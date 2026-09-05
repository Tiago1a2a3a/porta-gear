"""Setup único dos componentes usados pelo loop principal."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.modulo_database.database import BancoAcesso
from src.modulo_database.setup_database import CAMINHO_DATABASE_PADRAO, setup_database
from src.modulo_leitor.leitor import LeitorPN532
from src.modulo_leitor.setup_leitor import EXECUTAVEL_PADRAO, setup_leitor
from src.modulo_rele.rele import ConfiguracaoRele, ReleLuckfox
from src.modulo_rele.setup_rele import setup_rele


@dataclass(frozen=True)
class ConfiguracaoSistema:
    caminho_database: Path = CAMINHO_DATABASE_PADRAO
    numero_gpio_rele: int = 52
    quantidade_pulsos: int = 1
    tempo_rele_ligado: float = 1.0
    tempo_rele_desligado: float = 0.0
    executavel_leitor: Path = EXECUTAVEL_PADRAO
    timeout_setup_leitor: float = 10.0


@dataclass
class Sistema:
    database: BancoAcesso
    leitor: LeitorPN532
    rele: ReleLuckfox


def setup_sistema(configuracao: ConfiguracaoSistema) -> Sistema:
    """Inicializa relé, banco e leitor antes de iniciar o loop.

    O relé é preparado primeiro para colocar a saída no estado seguro o mais
    cedo possível. Nenhum dos setups é executado novamente dentro do loop.
    """
    configuracao_rele = ConfiguracaoRele(
        quantidade_pulsos=configuracao.quantidade_pulsos,
        tempo_ligado=configuracao.tempo_rele_ligado,
        tempo_desligado=configuracao.tempo_rele_desligado,
    )
    rele = setup_rele(
        numero_gpio=configuracao.numero_gpio_rele,
        configuracao=configuracao_rele,
    )
    database = setup_database(configuracao.caminho_database)
    leitor = setup_leitor(
        executavel=configuracao.executavel_leitor,
        timeout_setup=configuracao.timeout_setup_leitor,
    )

    return Sistema(
        database=database,
        leitor=leitor,
        rele=rele,
    )
