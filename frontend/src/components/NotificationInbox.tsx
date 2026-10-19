import {
  ActionIcon,
  Badge,
  Box,
  Card,
  Group,
  Stack,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconCheck, IconX } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { type Notification, type ReplayStatus, api } from "../api";

function formatTs(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function durationSince(from: string, to: string): string {
  const secs = Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  return `${mins}m ${secs % 60}s`;
}

interface Props {
  userId: string;
  replayStatus: ReplayStatus;
}

export function NotificationInbox({ userId, replayStatus }: Props) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    const fetch = async () => {
      const data = await api.notifications.list(userId);
      setNotifications(data);
    };
    fetch();
    const interval = setInterval(fetch, 500);
    return () => clearInterval(interval);
  }, [userId]);

  const handleMarkRead = async (notifId: string) => {
    await api.notifications.markRead(userId, notifId);
    setNotifications((prev) =>
      prev.map((n) => (n.notification_id === notifId ? { ...n, read: true } : n))
    );
  };

  const handleDismiss = async (notifId: string) => {
    await api.notifications.dismiss(userId, notifId);
    setNotifications((prev) => prev.filter((n) => n.notification_id !== notifId));
  };

  const unread = notifications.filter((n) => !n.read).length;

  return (
    <Box>
      <Group mb="sm">
        <Title order={5}>Inbox</Title>
        {unread > 0 && (
          <Badge color="red" size="sm">
            {unread} unread
          </Badge>
        )}
        {notifications.length === 0 && replayStatus.is_running && (
          <Text size="xs" c="dimmed">Waiting for events…</Text>
        )}
      </Group>

      {notifications.length === 0 && !replayStatus.is_running && replayStatus.current_index === 0 && (
        <Text size="sm" c="dimmed">
          Press Play to start the event replay and see notifications appear.
        </Text>
      )}

      <Stack gap="xs">
        {notifications.map((n) => {
          const isAdherence = n.config_label.toLowerCase().includes("adherence") ||
            n.message.toLowerCase().includes("adherence");
          const isSLA = n.message.toLowerCase().includes("sla");
          const borderColor = isSLA ? "red" : isAdherence ? "orange" : "blue";
          const isUnread = !n.read;

          return (
            <Card
              key={n.notification_id}
              withBorder
              p="sm"
              radius="md"
              style={{
                borderLeft: `3px solid var(--mantine-color-${borderColor}-6)`,
                opacity: isUnread ? 1 : 0.7,
              }}
            >
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Box style={{ flex: 1, minWidth: 0 }}>
                  <Group gap="xs" mb={4}>
                    <Badge size="xs" variant="light" color={borderColor}>
                      {n.config_label}
                    </Badge>
                    {n.is_shared && (
                      <Badge size="xs" variant="outline" color="violet">
                        From lead
                      </Badge>
                    )}
                    {isUnread && (
                      <Box
                        w={6}
                        h={6}
                        style={{ borderRadius: "50%", background: "var(--mantine-color-red-6)", flexShrink: 0 }}
                      />
                    )}
                  </Group>
                  <Text size="sm" fw={isUnread ? 600 : 400}>
                    {n.message}
                  </Text>
                  <Group gap="md" mt={4}>
                    <Text size="xs" c="dimmed">
                      Started {formatTs(n.triggered_at)}
                    </Text>
                    {n.last_seen_at !== n.triggered_at && (
                      <Text size="xs" c="dimmed">
                        · Active for {durationSince(n.triggered_at, n.last_seen_at)}
                      </Text>
                    )}
                  </Group>
                </Box>
                <Group gap="xs" style={{ flexShrink: 0 }}>
                  {isUnread && (
                    <Tooltip label="Mark as read">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="green"
                        onClick={() => handleMarkRead(n.notification_id)}
                      >
                        <IconCheck size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  <Tooltip label="Dismiss">
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="gray"
                      onClick={() => handleDismiss(n.notification_id)}
                    >
                      <IconX size={14} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
              </Group>
            </Card>
          );
        })}
      </Stack>
    </Box>
  );
}
