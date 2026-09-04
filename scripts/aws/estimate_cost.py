"""Reproducible conservative sandbox estimate; rates are explicit assumptions."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=float, default=4)
    p.add_argument("--fargate-vcpu-hour", type=float, default=0.012)
    p.add_argument("--fargate-gb-hour", type=float, default=0.0013)
    p.add_argument("--rds-hour", type=float, default=0.017)
    p.add_argument("--storage-month", type=float, default=0.12)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    # Four small Fargate tasks at 0.25 vCPU/0.5 GB for the timebox.
    fargate = 4 * args.hours * (args.fargate_vcpu_hour * 0.25 + args.fargate_gb_hour * 0.5)
    rds = args.hours * args.rds_hour
    storage = args.storage_month * (args.hours / (24 * 30))
    total = fargate + rds + storage
    result = {
        "calculated_at_utc": datetime.now(timezone.utc).isoformat(),
        "assumptions": {"hours": args.hours, "fargate_tasks": 4, "fargate_vcpu": 0.25, "fargate_memory_gb": 0.5, "rds_instances": 1, "rds_single_az": True, "interface_vpc_endpoints": 0, "nat_gateways": 0, "alb": 0, "rates_are_user_supplied_assumptions": True},
        "components_usd": {"fargate": round(fargate, 4), "rds": round(rds, 4), "storage_fraction": round(storage, 4)},
        "estimated_total_usd": round(total, 4),
        "operating_limit_usd": 10.0,
        "under_limit": total < 10.0,
        "not_included": ["taxes, regional data transfer, ECR storage beyond free allowance, CloudWatch ingestion, Security Hub charges, residual resource time"],
        "approval_required_before_first_billable_change": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
