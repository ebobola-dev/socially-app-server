class InitializeError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class ServerConfigNotInitializedError(InitializeError):
    def __init__(self):
        super().__init__("Server Config must be initialized first")


class UnableToGetEnvVariableError(InitializeError):
    def __init__(self, variables: tuple[str]):
        super().__init__(f"Unable to get the Env variables: {variables}")


class UnableToInitializeServiceError(InitializeError):
    def __init__(self, service_name: str):
        super().__init__(f"Unable to initialize [{service_name}]")


class ConfigNotInitalizedButUsingError(InitializeError):
    def __init__(self, config_name: str):
        super().__init__(
            f"Config [{config_name}] has not been initialized, but is being used"
        )


class UnableToInitalizeDatabaseError(InitializeError):
    def __init__(self):
        super().__init__("Unable to initalize database")


class DatabaseNotInitializedError(InitializeError):
    def __init__(self):
        super().__init__("Database has not beed initialized, but is being user")

class ServiceNotInitalizedButUsingError(InitializeError):
    def __init__(self, service_name: str):
        super().__init__(
            f"Service [{service_name}] has not been initialized, but is being used"
        )