class GatewayError(RuntimeError):
    pass


class AllProvidersFailed(GatewayError):
    pass