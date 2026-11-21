"""DFD Mermaid generator and GDPR Art. 30 / PIPL RoPA extractor."""

from __future__ import annotations

from collections import defaultdict

from dpia_as_code.models import (
    DataFlowModel,
    DataStore,
    ExternalEntity,
    MitigationStatus,
    ProcessNode,
    RoPAEntry,
)


def _escape_label(text: str) -> str:
    """Escape characters that can break Mermaid node or edge labels."""
    return text.replace('"', "'").replace("\n", " ").strip()


def generate_mermaid_dfd(model: DataFlowModel) -> str:
    """Generate a Mermaid flowchart representing the Data Flow Diagram (DFD)."""
    lines: list[str] = ["flowchart LR"]

    # Group nodes by trust_boundary (or default ungrouped zone)
    grouped: dict[str | None, list[ExternalEntity | ProcessNode | DataStore]] = defaultdict(list)
    for entity in model.entities:
        grouped[entity.trust_boundary].append(entity)
    for proc in model.processes:
        grouped[proc.trust_boundary].append(proc)
    for store in model.stores:
        grouped[store.trust_boundary].append(store)

    def _render_node(node: ExternalEntity | ProcessNode | DataStore, indent: str) -> str:
        region = model.resolve_region(node.id)
        label = _escape_label(f"{node.name} [{region}]")
        if isinstance(node, ExternalEntity):
            return f'{indent}{node.id}["{label}"]'
        if isinstance(node, ProcessNode):
            return f'{indent}{node.id}(("{label}"))'
        # DataStore: cylinder shape
        return f'{indent}{node.id}[("{label}")]'

    # Render nodes without trust boundary at root
    for node in grouped.pop(None, []):
        lines.append(_render_node(node, "    "))

    # Render trust boundary subgraphs deterministically
    for boundary in sorted(grouped.keys()):
        assert boundary is not None
        safe_sub_id = f"tb_{boundary.replace('-', '_').replace(' ', '_')}"
        lines.append(f'    subgraph {safe_sub_id}["Trust Boundary: {_escape_label(boundary)}"]')
        for node in grouped[boundary]:
            lines.append(_render_node(node, "        "))
        lines.append("    end")

    # Render data flows
    assets = model.data_asset_map()
    for flow in model.flows:
        asset_labels = ", ".join(assets[aid].id for aid in flow.data)
        tags: list[str] = []
        if not flow.encrypted_in_transit:
            tags.append("UNENCRYPTED")
        if model.is_cross_border_flow(flow):
            src_r = model.resolve_region(flow.source)
            dst_r = model.resolve_region(flow.target)
            tags.append(f"CROSS-BORDER {src_r}->{dst_r}")
        suffix = f" [{' | '.join(tags)}]" if tags else ""
        edge_label = _escape_label(f"{flow.name}: {asset_labels}{suffix}")
        arrow = "-.->" if not flow.encrypted_in_transit else "-->"
        lines.append(f'    {flow.source} {arrow}|"{edge_label}"| {flow.target}')

    return "\n".join(lines)


def generate_ropa(model: DataFlowModel) -> list[RoPAEntry]:
    """Extract GDPR Art. 30 & PIPL Record of Processing Activities (RoPA) entries per Process."""
    assets = model.data_asset_map()
    entities = {e.id: e for e in model.entities}
    stores = {s.id: s for s in model.stores}
    entries: list[RoPAEntry] = []

    for proc in model.processes:
        # Find flows touching this process
        touching_flows = [f for f in model.flows if f.source == proc.id or f.target == proc.id]

        # Collect data categories
        category_set: set[str] = set()
        for flow in touching_flows:
            for aid in flow.data:
                for cat in assets[aid].categories:
                    category_set.add(cat.value)

        # Collect third-party recipients & cross-border transfers outbound from this process
        recipients: list[str] = []
        cross_border: list[str] = []
        retention_policies: list[str] = []

        for flow in touching_flows:
            if flow.source == proc.id:
                target_entity = entities.get(flow.target)
                if target_entity and target_entity.is_third_party:
                    rec = f"{target_entity.name} ({target_entity.role.value}, {model.resolve_region(target_entity.id)})"
                    if rec not in recipients:
                        recipients.append(rec)

                target_store = stores.get(flow.target)
                if target_store:
                    ret_str = (
                        f"{target_store.name}: {target_store.retention_days} days"
                        if target_store.retention_days is not None
                        else f"{target_store.name}: indefinite (unspecified)"
                    )
                    if ret_str not in retention_policies:
                        retention_policies.append(ret_str)

            if model.is_cross_border_flow(flow):
                src_r = model.resolve_region(flow.source)
                dst_r = model.resolve_region(flow.target)
                cb = f"{flow.id} ({src_r} -> {dst_r}, mechanism={flow.transfer_mechanism.value})"
                if cb not in cross_border:
                    cross_border.append(cb)

        # Collect effective security measures applied to this process or wildcard
        security_measures: list[str] = []
        for mit in model.get_mitigations_for(proc.id):
            if mit.status in (MitigationStatus.IMPLEMENTED, MitigationStatus.VERIFIED):
                ctrl_prefix = f"[{mit.control_id}] " if mit.control_id else ""
                security_measures.append(f"{ctrl_prefix}{mit.pet_type.value} ({mit.status.value})")

        entries.append(
            RoPAEntry(
                process_id=proc.id,
                process_name=proc.name,
                controller=model.metadata.controller,
                dpo_contact=model.metadata.dpo_contact,
                purposes=list(proc.purposes),
                lawful_basis=proc.lawful_basis,
                data_subjects=[s.value for s in model.metadata.data_subjects],
                data_categories=sorted(category_set),
                recipients=recipients,
                cross_border_transfers=cross_border,
                retention_policies=retention_policies,
                security_measures=security_measures,
            )
        )

    return entries
