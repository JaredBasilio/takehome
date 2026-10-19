import {
  Badge,
  Box,
  Collapse,
  Group,
  Table,
  Text,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { type NotificationHistoryItem, type ReplayStatus, api } from "../api";

function formatTs(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function durationBetween(from: string, to: string): string {
  const secs = Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  return `${mins}m ${secs % 60}s`;
}

interface Props {
  userId: string;
  replayStatus: ReplayStatus;
}

export function NotificationHistory({ userId, replayStatus }: Props) {
  const [history, setHistory] = useState<NotificationHistoryItem[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      const data = await api.notifications.history(userId);
      setHistory(data);
      if (data.length > 0) setOpen(true);
    };
    fetch();
    const interval = setInterval(fetch, 1000);
    return () => clearInterval(interval);
  }, [userId]);

  if (history.length === 0) return null;

  return (
    <Box>
      <UnstyledButton onClick={() => setOpen((o) => !o)} style={{ width: "100%" }}>
        <Group mb="sm">
          {open ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
          <Title order={5}>History</Title>
          <Badge variant="light" color="gray" size="sm">
            {history.length} resolved
          </Badge>
        </Group>
      </UnstyledButton>

      <Collapse in={open}>
        <Table striped highlightOnHover withTableBorder withColumnBorders fz="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Rule</Table.Th>
              <Table.Th>Message</Table.Th>
              <Table.Th>Triggered</Table.Th>
              <Table.Th>Resolved</Table.Th>
              <Table.Th>Duration</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {[...history].reverse().map((item) => (
              <Table.Tr key={item.notification_id}>
                <Table.Td>
                  <Text size="xs" fw={500}>
                    {item.config_label}
                  </Text>
                  {item.is_shared && (
                    <Badge size="xs" variant="outline" color="violet" mt={2}>
                      From lead
                    </Badge>
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="xs">{item.message}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed">
                    {formatTs(item.triggered_at)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed">
                    {item.resolved_by_event_id === "user_dismissed"
                      ? "Dismissed"
                      : formatTs(item.resolved_at)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed">
                    {item.resolved_by_event_id === "user_dismissed"
                      ? "—"
                      : durationBetween(item.triggered_at, item.resolved_at)}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Collapse>
    </Box>
  );
}
