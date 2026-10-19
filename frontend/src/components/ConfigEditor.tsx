import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Checkbox,
  Group,
  Modal,
  NumberInput,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconEdit, IconPlus, IconSend, IconTrash } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import {
  type CreateConfigPayload,
  type NotificationConfig,
  type User,
  api,
} from "../api";

const EVENT_FIELDS: Record<string, { label: string; value: string; inputType: "number" | "boolean" | "text" }[]> = {
  queue_snapshot: [
    { label: "Tickets waiting", value: "tickets_waiting", inputType: "number" },
    { label: "Longest wait (sec)", value: "longest_wait_sec", inputType: "number" },
    { label: "Agents available", value: "agents_available", inputType: "number" },
  ],
  adherence_check: [
    { label: "In violation", value: "in_violation", inputType: "boolean" },
  ],
  agent_state_change: [
    { label: "Previous state duration (sec)", value: "previous_state_duration_sec", inputType: "number" },
  ],
};

const COMPARATORS = [
  { label: ">", value: "gt" },
  { label: "<", value: "lt" },
  { label: "≥", value: "gte" },
  { label: "≤", value: "lte" },
  { label: "=", value: "eq" },
  { label: "≠", value: "neq" },
];

interface Props {
  user: User;
}

interface FormState {
  label: string;
  event_type: string;
  field: string;
  comparator: string;
  value: string;
  value_mode: "absolute" | "pct_of_sla";
  scope_queue_ids: string;
  scope_agent_ids: string;
}

const DEFAULT_FORM: FormState = {
  label: "",
  event_type: "queue_snapshot",
  field: "tickets_waiting",
  comparator: "gt",
  value: "10",
  value_mode: "absolute",
  scope_queue_ids: "",
  scope_agent_ids: "",
};

export function ConfigEditor({ user }: Props) {
  const [configs, setConfigs] = useState<NotificationConfig[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);

  const fetchConfigs = async () => {
    const data = await api.configs.list(user.id);
    setConfigs(data);
  };

  useEffect(() => {
    fetchConfigs();
  }, [user.id]);

  const ownedConfigs = configs.filter((c) => c.owner_id === user.id);
  const sharedToMe = configs.filter(
    (c) => c.owner_id !== user.id && c.assigned_to_recipient_ids.includes(user.id)
  );

  const openCreate = () => {
    setEditing(null);
    const defaultField = user.role === "agent" ? "in_violation" : "tickets_waiting";
    const defaultType = user.role === "agent" ? "adherence_check" : "queue_snapshot";
    setForm({
      ...DEFAULT_FORM,
      event_type: defaultType,
      field: defaultField,
      scope_agent_ids: user.role === "agent" ? user.id : "",
    });
    setModalOpen(true);
  };

  const openEdit = (config: NotificationConfig) => {
    setEditing(config.id);
    setForm({
      label: config.label,
      event_type: config.event_type,
      field: config.field,
      comparator: config.comparator,
      value: String(config.value),
      value_mode: config.value_mode,
      scope_queue_ids: config.scope?.queue_ids?.join(", ") ?? "",
      scope_agent_ids: config.scope?.agent_ids?.join(", ") ?? "",
    });
    setModalOpen(true);
  };

  const buildPayload = (): CreateConfigPayload => {
    const fieldDef = (EVENT_FIELDS[form.event_type] ?? []).find((f) => f.value === form.field);
    let parsedValue: unknown = form.value;
    if (fieldDef?.inputType === "number") parsedValue = parseFloat(form.value);
    if (fieldDef?.inputType === "boolean") parsedValue = form.value === "true";

    const queueIds = form.scope_queue_ids.split(",").map((s) => s.trim()).filter(Boolean);
    const agentIds = form.scope_agent_ids.split(",").map((s) => s.trim()).filter(Boolean);

    return {
      label: form.label || `${form.field} ${form.comparator} ${form.value}`,
      event_type: form.event_type,
      field: form.field,
      comparator: form.comparator,
      value: parsedValue,
      value_mode: form.value_mode,
      scope: queueIds.length || agentIds.length
        ? { queue_ids: queueIds.length ? queueIds : null, agent_ids: agentIds.length ? agentIds : null }
        : null,
    };
  };

  const handleSave = async () => {
    const payload = buildPayload();
    try {
      if (editing) {
        await api.configs.update(user.id, editing, payload);
      } else {
        await api.configs.create(user.id, payload);
      }
      setModalOpen(false);
      fetchConfigs();
    } catch (e) {
      alert(String(e));
    }
  };

  const handleDelete = async (configId: string) => {
    if (!confirm("Delete this rule?")) return;
    await api.configs.delete(user.id, configId);
    fetchConfigs();
  };

  const handlePush = async (configId: string) => {
    await api.configs.push(user.id, configId);
    fetchConfigs();
  };

  const currentFields = EVENT_FIELDS[form.event_type] ?? [];
  const currentField = currentFields.find((f) => f.value === form.field);
  const showPctOfSla = form.field === "longest_wait_sec";

  const canPush = user.role === "team_lead" || user.role === "head_of_support";

  return (
    <Box>
      <Group mb="sm" justify="space-between">
        <Title order={5}>Notification Rules</Title>
        <Button size="xs" leftSection={<IconPlus size={14} />} onClick={openCreate}>
          Add Rule
        </Button>
      </Group>

      {ownedConfigs.length === 0 && sharedToMe.length === 0 ? (
        <Text size="sm" c="dimmed">No rules configured.</Text>
      ) : (
        <Table withTableBorder withColumnBorders fz="xs" mb="md">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Label</Table.Th>
              <Table.Th>Event</Table.Th>
              <Table.Th>Condition</Table.Th>
              <Table.Th>Scope</Table.Th>
              <Table.Th>Assigned to</Table.Th>
              <Table.Th w={80}>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {ownedConfigs.map((config) => (
              <ConfigRow
                key={config.id}
                config={config}
                isOwner
                canPush={canPush}
                onEdit={() => openEdit(config)}
                onDelete={() => handleDelete(config.id)}
                onPush={() => handlePush(config.id)}
              />
            ))}
            {sharedToMe.map((config) => (
              <ConfigRow
                key={config.id}
                config={config}
                isOwner={false}
                canPush={false}
                onEdit={() => {}}
                onDelete={() => {}}
                onPush={() => {}}
              />
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Edit Rule" : "New Notification Rule"}
        size="md"
      >
        <Stack gap="sm">
          <TextInput
            label="Label"
            placeholder="Describe this rule"
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
          />

          <Select
            label="Event type"
            value={form.event_type}
            onChange={(v) => {
              const t = v ?? "queue_snapshot";
              const firstField = (EVENT_FIELDS[t] ?? [])[0]?.value ?? "";
              setForm({ ...form, event_type: t, field: firstField });
            }}
            data={[
              { label: "Queue snapshot", value: "queue_snapshot" },
              { label: "Agent state change", value: "agent_state_change" },
              { label: "Adherence check", value: "adherence_check" },
            ]}
          />

          <Group grow>
            <Select
              label="Field"
              value={form.field}
              onChange={(v) => setForm({ ...form, field: v ?? "" })}
              data={currentFields.map((f) => ({ label: f.label, value: f.value }))}
            />
            <Select
              label="Comparator"
              value={form.comparator}
              onChange={(v) => setForm({ ...form, comparator: v ?? "gt" })}
              data={COMPARATORS}
            />
          </Group>

          {currentField?.inputType === "boolean" ? (
            <Select
              label="Value"
              value={form.value}
              onChange={(v) => setForm({ ...form, value: v ?? "true" })}
              data={[
                { label: "True", value: "true" },
                { label: "False", value: "false" },
              ]}
            />
          ) : (
            <NumberInput
              label="Value"
              value={parseFloat(form.value) || 0}
              onChange={(v) => setForm({ ...form, value: String(v) })}
            />
          )}

          {showPctOfSla && (
            <Checkbox
              label="Value is % of SLA target (e.g. 80 = 80% of sla_target_sec)"
              checked={form.value_mode === "pct_of_sla"}
              onChange={(e) =>
                setForm({ ...form, value_mode: e.target.checked ? "pct_of_sla" : "absolute" })
              }
            />
          )}

          {user.role !== "agent" && (
            <TextInput
              label="Queue scope (comma-separated, blank = all)"
              placeholder="billing, tier_2"
              value={form.scope_queue_ids}
              onChange={(e) => setForm({ ...form, scope_queue_ids: e.target.value })}
            />
          )}

          <TextInput
            label="Agent scope (comma-separated, blank = all)"
            placeholder="a_19, a_07"
            value={form.scope_agent_ids}
            onChange={(e) => setForm({ ...form, scope_agent_ids: e.target.value })}
          />

          <Group justify="flex-end" mt="sm">
            <Button variant="subtle" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSave}>{editing ? "Save" : "Create"}</Button>
          </Group>
        </Stack>
      </Modal>
    </Box>
  );
}

interface RowProps {
  config: NotificationConfig;
  isOwner: boolean;
  canPush: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPush: () => void;
}

function ConfigRow({ config, isOwner, canPush, onEdit, onDelete, onPush }: RowProps) {
  const comparatorLabel = COMPARATORS.find((c) => c.value === config.comparator)?.label ?? config.comparator;
  const valueDisplay =
    config.value_mode === "pct_of_sla" ? `${config.value}% of SLA` : String(config.value);
  const scopeParts: string[] = [];
  if (config.scope?.queue_ids?.length) scopeParts.push(`queues: ${config.scope.queue_ids.join(", ")}`);
  if (config.scope?.agent_ids?.length) scopeParts.push(`agents: ${config.scope.agent_ids.join(", ")}`);

  return (
    <Table.Tr>
      <Table.Td>
        <Text size="xs" fw={500}>
          {config.label}
        </Text>
        {config.is_shared && (
          <Badge size="xs" variant="outline" color="violet" mt={2}>Shared</Badge>
        )}
        {!isOwner && (
          <Badge size="xs" variant="light" color="gray" mt={2}>From lead</Badge>
        )}
      </Table.Td>
      <Table.Td>
        <Text size="xs" c="dimmed">{config.event_type.replace(/_/g, " ")}</Text>
      </Table.Td>
      <Table.Td>
        <Text size="xs" ff="monospace">
          {config.field} {comparatorLabel} {valueDisplay}
        </Text>
      </Table.Td>
      <Table.Td>
        <Text size="xs" c="dimmed">
          {scopeParts.length ? scopeParts.join("; ") : "all"}
        </Text>
      </Table.Td>
      <Table.Td>
        <Text size="xs" c="dimmed">
          {config.assigned_to_recipient_ids.length} user{config.assigned_to_recipient_ids.length !== 1 ? "s" : ""}
        </Text>
      </Table.Td>
      <Table.Td>
        {isOwner ? (
          <Group gap={4}>
            <Tooltip label="Edit">
              <ActionIcon size="xs" variant="subtle" onClick={onEdit}>
                <IconEdit size={12} />
              </ActionIcon>
            </Tooltip>
            {canPush && (
              <Tooltip label="Push to agents">
                <ActionIcon size="xs" variant="subtle" color="violet" onClick={onPush}>
                  <IconSend size={12} />
                </ActionIcon>
              </Tooltip>
            )}
            <Tooltip label="Delete">
              <ActionIcon size="xs" variant="subtle" color="red" onClick={onDelete}>
                <IconTrash size={12} />
              </ActionIcon>
            </Tooltip>
          </Group>
        ) : (
          <Text size="xs" c="dimmed">Read-only</Text>
        )}
      </Table.Td>
    </Table.Tr>
  );
}
