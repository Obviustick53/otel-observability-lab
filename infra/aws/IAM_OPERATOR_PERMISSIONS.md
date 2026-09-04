# Permisos del operador AWS

La persona que ejecute el runbook debe usar una identidad separada del runtime
de las tareas. Los roles ECS y Flow Logs son creados por CloudFormation; las
tareas no reciben permisos de operador.

El permiso sensible `iam:PassRole` debe limitarse a los cuatro roles creados por
estas capas, nunca a `Resource: "*"`:

```text
arn:aws:iam::<ACCOUNT_ID>:role/<ProjectName>-<Environment>-ecs-execution
arn:aws:iam::<ACCOUNT_ID>:role/<ProjectName>-<Environment>-app-task
arn:aws:iam::<ACCOUNT_ID>:role/<ProjectName>-<Environment>-collector-task
arn:aws:iam::<ACCOUNT_ID>:role/<ProjectName>-<Environment>-flow-logs
```

En la política del operador, acompañar ese statement con:

```json
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": [
    "arn:aws:iam::<ACCOUNT_ID>:role/<ProjectName>-<Environment>-ecs-execution",
    "arn:aws:iam::<ACCOUNT_ID>:role/<ProjectName>-<Environment>-app-task",
    "arn:aws:iam::<ACCOUNT_ID>:role/<ProjectName>-<Environment>-collector-task",
    "arn:aws:iam::<ACCOUNT_ID>:role/<ProjectName>-<Environment>-flow-logs"
  ],
  "Condition": {
    "StringLike": {
      "iam:PassedToService": [
        "ecs-tasks.amazonaws.com",
        "vpc-flow-logs.amazonaws.com"
      ]
    }
  }
}
```

El resto del acceso debe concederse solo para los servicios y recursos del
proyecto: `cloudformation` sobre los cinco stacks exactos, ECR sobre los cuatro
repositorios, ECS/RDS/CloudWatch/EC2/CloudTrail/Security Hub de la región
esperada y `iam:CreateRole`, `iam:PutRolePolicy`, `iam:TagRole` para los roles
de nombre exacto. La plantilla no adjunta una política administrativa ni
consulta secretos plaintext.

`iam:PassRole` no autoriza por sí mismo a desplegar: los scripts siguen
exigiendo preflight, cuenta/región esperadas y la cadena
`I_HAVE_REVIEWED_COST_AND_PLAN`. La cadena no sustituye una autorización IAM.
