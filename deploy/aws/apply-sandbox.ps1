<#
.SYNOPSIS
    Compatibilidad histórica bloqueada para despliegues AWS.
.DESCRIPTION
    La ruta operativa única es scripts/aws/apply.ps1, que consume la familia
    CloudFormation 00-05, exige preflight y una confirmación explícita. Este
    archivo se conserva para no romper enlaces antiguos, pero nunca ejecuta
    infraestructura.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
throw 'Esta entrada histórica está bloqueada. Use scripts/aws/apply.ps1 con la familia CloudFormation 00-05 y sus guardas de autorización.'
