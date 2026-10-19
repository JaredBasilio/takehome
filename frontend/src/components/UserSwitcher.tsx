import { Avatar, Badge, Box, NavLink, Stack, Text } from "@mantine/core";
import { useEffect, useState } from "react";
import { type Notification, type User, api } from "../api";

const ROLE_COLORS: Record<string, string> = {
  agent: "blue",
  team_lead: "violet",
  head_of_support: "orange",
};

const ROLE_LABELS: Record<string, string> = {
  agent: "Agent",
  team_lead: "Team Lead",
  head_of_support: "Head of Support",
};

interface Props {
  users: User[];
  activeUserId: string;
  onSelect: (id: string) => void;
}

export function UserSwitcher({ users, activeUserId, onSelect }: Props) {
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    if (users.length === 0) return;

    const fetchCounts = async () => {
      const counts: Record<string, number> = {};
      await Promise.all(
        users.map(async (u) => {
          const notifs: Notification[] = await api.notifications.list(u.user_id);
          counts[u.user_id] = notifs.filter((n) => !n.read).length;
        })
      );
      setUnreadCounts(counts);
    };

    fetchCounts();
    const interval = setInterval(fetchCounts, 1000);
    return () => clearInterval(interval);
  }, [users]);

  return (
    <Stack gap={4}>
      <Text size="xs" fw={600} c="dimmed" px="xs" pt="xs" tt="uppercase">
        Team Members
      </Text>
      {users.map((user) => {
        const unread = unreadCounts[user.user_id] ?? 0;
        const initials = user.name
          .split(" ")
          .map((n) => n[0])
          .join("")
          .toUpperCase();

        return (
          <NavLink
            key={user.user_id}
            active={user.user_id === activeUserId}
            onClick={() => onSelect(user.user_id)}
            label={
              <Box>
                <Text size="sm" fw={500} lh={1.3}>
                  {user.name}
                </Text>
                <Badge
                  size="xs"
                  variant="light"
                  color={ROLE_COLORS[user.role] ?? "gray"}
                  mt={2}
                >
                  {ROLE_LABELS[user.role] ?? user.role}
                </Badge>
              </Box>
            }
            leftSection={
              <Avatar size={32} radius="xl" color={ROLE_COLORS[user.role] ?? "gray"}>
                {initials}
              </Avatar>
            }
            rightSection={
              unread > 0 ? (
                <Badge size="sm" color="red" variant="filled" circle>
                  {unread}
                </Badge>
              ) : null
            }
            style={{ borderRadius: 8 }}
          />
        );
      })}
    </Stack>
  );
}
