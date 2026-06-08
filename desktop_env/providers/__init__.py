from desktop_env.providers.base import VMManager, Provider


def create_vm_manager_and_provider(provider_name: str, region: str, use_proxy: bool = False):
    """
    Factory function to get the Virtual Machine Manager and Provider instances based on the provided provider name.
    """
    provider_name = provider_name.lower().strip()
    if provider_name == "vmware":
        from desktop_env.providers.vmware.manager import VMwareVMManager
        from desktop_env.providers.vmware.provider import VMwareProvider
        return VMwareVMManager(), VMwareProvider(region)
    elif provider_name == "virtualbox":
        from desktop_env.providers.virtualbox.manager import VirtualBoxVMManager
        from desktop_env.providers.virtualbox.provider import VirtualBoxProvider
        return VirtualBoxVMManager(), VirtualBoxProvider(region)
    elif provider_name in ["aws", "amazon web services"]:
        from desktop_env.providers.aws.manager import AWSVMManager
        from desktop_env.providers.aws.provider import AWSProvider
        return AWSVMManager(), AWSProvider(region)
    elif provider_name == "azure":
        from desktop_env.providers.azure.manager import AzureVMManager
        from desktop_env.providers.azure.provider import AzureProvider
        return AzureVMManager(), AzureProvider(region)
    elif provider_name == "docker":
        from desktop_env.providers.docker.manager import DockerVMManager
        from desktop_env.providers.docker.provider import DockerProvider
        return DockerVMManager(), DockerProvider(region)
    elif provider_name == "utm":
        from desktop_env.providers.utm.manager import UTMVMManager
        from desktop_env.providers.utm.provider import UTMProvider
        return UTMVMManager(), UTMProvider()
    else:
        raise NotImplementedError(f"{provider_name} not implemented!")