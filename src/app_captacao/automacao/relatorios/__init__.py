from app_captacao.automacao.relatorios.registro import obter_executor


def executar_relatorio_dedicado(executor_relatorio, driver, wait, relatorio_config, contexto):
    executor = obter_executor(executor_relatorio)
    if not executor:
        raise ValueError(f"Executor de relatorio nao suportado: {executor_relatorio}")

    return executor(driver, wait, relatorio_config, contexto)
