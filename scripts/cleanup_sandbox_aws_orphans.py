#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys


def run_aws(region: str, aws_args: list[str], expect_json: bool = True, allow_missing: bool = False):
    command = ["aws", *aws_args, "--region", region]
    if expect_json:
        command.extend(["--output", "json"])

    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        if allow_missing and any(
            marker in stderr
            for marker in (
                "ResourceNotFoundException",
                "NoSuchEntity",
                "ValidationError",
                "AutoScalingGroup name not found",
                "does not exist",
                "InvalidInstanceID.NotFound",
                "InvalidGroup.NotFound",
                "InvalidSecurityGroupID.NotFound",
                "InvalidNetworkInterfaceID.NotFound",
                "LoadBalancerNotFound",
                "TargetGroupNotFound",
                "InvalidVpcEndpointId.NotFound",
                "InvalidVpcPeeringConnectionID.NotFound",
                "InvalidVolume.NotFound",
            )
        ):
            return None
        raise SystemExit(
            "AWS CLI command failed:\n"
            f"  command: {' '.join(command)}\n"
            f"  stderr: {stderr or completed.stdout.strip()}"
        )

    if not expect_json:
        return completed.stdout.strip()

    payload = completed.stdout.strip()
    return json.loads(payload) if payload else {}


def tag_map(tags: list[dict[str, str]] | None) -> dict[str, str]:
    return {item.get("Key", ""): item.get("Value", "") for item in (tags or [])}


def has_cluster_marker(
    tags: list[dict[str, str]] | None,
    cluster_name: str,
    environment_identity: str,
) -> bool:
    tags_by_key = tag_map(tags)
    return any(
        (
            key == "eks:cluster-name" and value == cluster_name
        )
        or (
            key == "facedetector:cluster-name" and value == cluster_name
        )
        or (
            key == "facedetector:identity" and value == environment_identity
        )
        or (
            key == f"k8s.io/cluster-autoscaler/{cluster_name}" and value == "owned"
        )
        or (
            key == f"kubernetes.io/cluster/{cluster_name}" and value in {"owned", "shared"}
        )
        for key, value in tags_by_key.items()
    )


def cleanup_nodegroups(region: str, cluster_name: str, environment_identity: str) -> None:
    cluster = run_aws(
        region,
        ["eks", "describe-cluster", "--name", cluster_name],
        allow_missing=True,
    )
    if cluster is None:
        print(f"Cluster {cluster_name} does not exist. Skipping nodegroup cleanup.")
        return

    response = run_aws(region, ["eks", "list-nodegroups", "--cluster-name", cluster_name])
    nodegroups = response.get("nodegroups", [])
    if not nodegroups:
        print(f"No EKS nodegroups found for {cluster_name}.")
        return

    for nodegroup in nodegroups:
        print(f"Deleting orphaned or leftover nodegroup {nodegroup} in cluster {cluster_name}.")
        run_aws(
            region,
            ["eks", "delete-nodegroup", "--cluster-name", cluster_name, "--nodegroup-name", nodegroup],
            expect_json=False,
            allow_missing=True,
        )


def cleanup_autoscaling_groups(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(region, ["autoscaling", "describe-auto-scaling-groups"])
    matched = [
        group["AutoScalingGroupName"]
        for group in response.get("AutoScalingGroups", [])
        if has_cluster_marker(group.get("Tags"), cluster_name, environment_identity)
    ]

    if not matched:
        print(f"No Auto Scaling groups tagged for sandbox cluster {cluster_name}.")
        return

    for group_name in matched:
        print(f"Force deleting Auto Scaling group {group_name} for sandbox cluster {cluster_name}.")
        run_aws(
            region,
            [
                "autoscaling",
                "update-auto-scaling-group",
                "--auto-scaling-group-name",
                group_name,
                "--min-size",
                "0",
                "--max-size",
                "0",
                "--desired-capacity",
                "0",
            ],
            expect_json=False,
            allow_missing=True,
        )
        run_aws(
            region,
            [
                "autoscaling",
                "delete-auto-scaling-group",
                "--auto-scaling-group-name",
                group_name,
                "--force-delete",
            ],
            expect_json=False,
            allow_missing=True,
        )


def cleanup_instances(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(
        region,
        [
            "ec2",
            "describe-instances",
            "--filters",
            "Name=instance-state-name,Values=pending,running,stopping,stopped",
        ],
    )

    instance_ids: list[str] = []
    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            if has_cluster_marker(instance.get("Tags"), cluster_name, environment_identity):
                instance_ids.append(instance["InstanceId"])

    if not instance_ids:
        print(f"No EC2 instances tagged for sandbox cluster {cluster_name}.")
        return

    print(
        "Terminating EC2 instances still tagged for sandbox cluster "
        f"{cluster_name}: {', '.join(instance_ids)}"
    )
    run_aws(
        region,
        ["ec2", "terminate-instances", "--instance-ids", *instance_ids],
        allow_missing=True,
    )


def cleanup_elbv2_load_balancers(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(region, ["elbv2", "describe-load-balancers"])
    matched: list[tuple[str, str]] = []

    for load_balancer in response.get("LoadBalancers", []):
        arn = load_balancer["LoadBalancerArn"]
        tags_response = run_aws(
            region,
            ["elbv2", "describe-tags", "--resource-arns", arn],
            allow_missing=True,
        )
        tag_descriptions = tags_response.get("TagDescriptions", []) if tags_response else []
        tags = tag_descriptions[0].get("Tags", []) if tag_descriptions else []
        if has_cluster_marker(tags, cluster_name, environment_identity):
            matched.append((load_balancer["LoadBalancerName"], arn))

    if not matched:
        print(f"No ELBv2 load balancers tagged for sandbox cluster {cluster_name}.")
        return

    for name, arn in matched:
        print(f"Deleting ELBv2 load balancer {name} for sandbox cluster {cluster_name}.")
        run_aws(
            region,
            ["elbv2", "delete-load-balancer", "--load-balancer-arn", arn],
            expect_json=False,
            allow_missing=True,
        )


def cleanup_classic_load_balancers(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(region, ["elb", "describe-load-balancers"])
    matched: list[str] = []

    for load_balancer in response.get("LoadBalancerDescriptions", []):
        name = load_balancer["LoadBalancerName"]
        tags_response = run_aws(
            region,
            ["elb", "describe-tags", "--load-balancer-names", name],
            allow_missing=True,
        )
        descriptions = tags_response.get("TagDescriptions", []) if tags_response else []
        tags = descriptions[0].get("Tags", []) if descriptions else []
        if has_cluster_marker(tags, cluster_name, environment_identity):
            matched.append(name)

    if not matched:
        print(f"No classic ELBs tagged for sandbox cluster {cluster_name}.")
        return

    for name in matched:
        print(f"Deleting classic ELB {name} for sandbox cluster {cluster_name}.")
        run_aws(
            region,
            ["elb", "delete-load-balancer", "--load-balancer-name", name],
            expect_json=False,
            allow_missing=True,
        )


def cleanup_available_volumes(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(
        region,
        [
            "ec2",
            "describe-volumes",
            "--filters",
            "Name=status,Values=available",
        ],
    )
    matched = [
        volume["VolumeId"]
        for volume in response.get("Volumes", [])
        if has_cluster_marker(volume.get("Tags"), cluster_name, environment_identity)
    ]

    if not matched:
        print(f"No available EBS volumes tagged for sandbox cluster {cluster_name}.")
        return

    for volume_id in matched:
        print(f"Deleting orphaned EBS volume {volume_id} for sandbox cluster {cluster_name}.")
        run_aws(
            region,
            ["ec2", "delete-volume", "--volume-id", volume_id],
            expect_json=False,
            allow_missing=True,
        )


def cleanup_available_network_interfaces(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(
        region,
        [
            "ec2",
            "describe-network-interfaces",
            "--filters",
            "Name=status,Values=available",
        ],
    )
    matched = [
        interface["NetworkInterfaceId"]
        for interface in response.get("NetworkInterfaces", [])
        if has_cluster_marker(interface.get("TagSet") or interface.get("Tags"), cluster_name, environment_identity)
    ]

    if not matched:
        print(f"No available network interfaces tagged for sandbox cluster {cluster_name}.")
        return

    for interface_id in matched:
        print(f"Deleting available network interface {interface_id} for sandbox cluster {cluster_name}.")
        run_aws(
            region,
            ["ec2", "delete-network-interface", "--network-interface-id", interface_id],
            expect_json=False,
            allow_missing=True,
        )


def cleanup_vpc_endpoints(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(region, ["ec2", "describe-vpc-endpoints"])
    matched = [
        endpoint["VpcEndpointId"]
        for endpoint in response.get("VpcEndpoints", [])
        if endpoint.get("State") not in {"deleted", "deleting"}
        and has_cluster_marker(endpoint.get("Tags"), cluster_name, environment_identity)
    ]

    if not matched:
        print(f"No VPC endpoints tagged for sandbox cluster {cluster_name}.")
        return

    print(
        "Deleting VPC endpoints tagged for sandbox cluster "
        f"{cluster_name}: {', '.join(matched)}"
    )
    run_aws(
        region,
        ["ec2", "delete-vpc-endpoints", "--vpc-endpoint-ids", *matched],
        allow_missing=True,
    )


def cleanup_vpc_peering_connections(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(region, ["ec2", "describe-vpc-peering-connections"])
    matched = [
        connection["VpcPeeringConnectionId"]
        for connection in response.get("VpcPeeringConnections", [])
        if connection.get("Status", {}).get("Code") not in {"deleted", "rejected", "failed"}
        and has_cluster_marker(connection.get("Tags"), cluster_name, environment_identity)
    ]

    if not matched:
        print(f"No VPC peering connections tagged for sandbox cluster {cluster_name}.")
        return

    for connection_id in matched:
        print(f"Deleting VPC peering connection {connection_id} for sandbox cluster {cluster_name}.")
        run_aws(
            region,
            ["ec2", "delete-vpc-peering-connection", "--vpc-peering-connection-id", connection_id],
            expect_json=False,
            allow_missing=True,
        )


def cleanup_security_groups(region: str, cluster_name: str, environment_identity: str) -> None:
    response = run_aws(region, ["ec2", "describe-security-groups"])
    matched = [
        group
        for group in response.get("SecurityGroups", [])
        if group.get("GroupName") != "default"
        and has_cluster_marker(group.get("Tags"), cluster_name, environment_identity)
    ]

    if not matched:
        print(f"No non-default security groups tagged for sandbox cluster {cluster_name}.")
        return

    for group in matched:
        group_id = group["GroupId"]
        group_name = group.get("GroupName", group_id)
        interfaces = run_aws(
            region,
            ["ec2", "describe-network-interfaces", "--filters", f"Name=group-id,Values={group_id}"],
        )
        attached_interfaces = interfaces.get("NetworkInterfaces", [])
        if attached_interfaces:
            print(
                f"Security group {group_name} ({group_id}) is still attached to "
                f"{len(attached_interfaces)} network interface(s). Skipping for now."
            )
            continue

        print(f"Deleting orphaned security group {group_name} ({group_id}) for sandbox cluster {cluster_name}.")
        try:
            run_aws(
                region,
                ["ec2", "delete-security-group", "--group-id", group_id],
                expect_json=False,
                allow_missing=True,
            )
        except SystemExit as exc:
            error_text = str(exc)
            if "DependencyViolation" in error_text or "InvalidGroup.InUse" in error_text:
                print(
                    f"Security group {group_name} ({group_id}) is still in use by another AWS dependency. "
                    "Skipping for now."
                )
                continue
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--cluster-name", required=True)
    parser.add_argument("--environment-identity", default="")
    args = parser.parse_args()
    environment_identity = args.environment_identity or args.cluster_name

    cleanup_nodegroups(args.region, args.cluster_name, environment_identity)
    cleanup_autoscaling_groups(args.region, args.cluster_name, environment_identity)
    cleanup_instances(args.region, args.cluster_name, environment_identity)
    cleanup_elbv2_load_balancers(args.region, args.cluster_name, environment_identity)
    cleanup_classic_load_balancers(args.region, args.cluster_name, environment_identity)
    cleanup_available_volumes(args.region, args.cluster_name, environment_identity)
    cleanup_available_network_interfaces(args.region, args.cluster_name, environment_identity)
    cleanup_vpc_endpoints(args.region, args.cluster_name, environment_identity)
    cleanup_vpc_peering_connections(args.region, args.cluster_name, environment_identity)
    cleanup_security_groups(args.region, args.cluster_name, environment_identity)
    print(f"Finished sandbox AWS orphan cleanup for {args.cluster_name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())