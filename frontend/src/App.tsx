import { AppShell, Box, Group, Stack, Text, Title } from "@mantine/core";
import { TimelineScrubber } from "./components/TimelineScrubber";
import { IconBell } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { type ReplayStatus, type User, api } from "./api";
import { ConfigEditor } from "./components/ConfigEditor";
import { NotificationHistory } from "./components/NotificationHistory";
import { NotificationInbox } from "./components/NotificationInbox";
import { ReplayControls } from "./components/ReplayControls";
import { UserSwitcher } from "./components/UserSwitcher";

export default function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [activeUserId, setActiveUserId] = useState<string>("");
  const [replayStatus, setReplayStatus] = useState<ReplayStatus>({
    is_running: false,
    current_index: 0,
    total_events: 0,
    current_ts: null,
    speed: "normal",
  });

  useEffect(() => {
    api.users.list().then((u) => {
      setUsers(u);
      if (u.length > 0) setActiveUserId(u[0].id);
    });
  }, []);

  // Poll replay status while running
  useEffect(() => {
    const interval = setInterval(async () => {
      const status = await api.replay.status();
      setReplayStatus(status);
    }, 500);
    return () => clearInterval(interval);
  }, []);

  const activeUser = users.find((u) => u.id === activeUserId);

  return (
    <AppShell
      navbar={{ width: 240, breakpoint: "sm" }}
      header={{ height: 84 }}
      padding="md"
    >
      <AppShell.Header px="md" py="xs">
        <Group justify="space-between" align="center" mb={4}>
          <Group gap="xs">
            <IconBell size={20} color="var(--mantine-color-blue-6)" />
            <Title order={4} c="dark">Intraday Notifications</Title>
          </Group>
          <ReplayControls status={replayStatus} onStatusChange={setReplayStatus} />
        </Group>
        <TimelineScrubber status={replayStatus} onStatusChange={setReplayStatus} />
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        <UserSwitcher
          users={users}
          activeUserId={activeUserId}
          onSelect={setActiveUserId}
        />
      </AppShell.Navbar>

      <AppShell.Main bg="gray.0">
        {activeUser ? (
          <Stack gap="md">
            <Box>
              <Title order={3} mb="xs">
                {activeUser.name}
              </Title>
              <Text size="sm" c="dimmed" tt="capitalize">
                {activeUser.role.replace(/_/g, " ")}
                {activeUser.queue_memberships.length > 0
                  ? ` · queues: ${activeUser.queue_memberships.map((m) => m.queue_id).join(", ")}`
                  : ""}
              </Text>
            </Box>

            <NotificationInbox userId={activeUserId} replayStatus={replayStatus} />
            <NotificationHistory userId={activeUserId} replayStatus={replayStatus} />
            <ConfigEditor user={activeUser} />
          </Stack>
        ) : (
          <Text c="dimmed">Select a user</Text>
        )}
      </AppShell.Main>
    </AppShell>
  );
}
