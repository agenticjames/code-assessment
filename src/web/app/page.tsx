import { Activity, CreditCard, DollarSign, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const stats = [
  {
    title: "Total Revenue",
    value: "$45,231.89",
    change: "+20.1%",
    hint: "from last month",
    icon: DollarSign,
  },
  {
    title: "Subscriptions",
    value: "+2,350",
    change: "+180.1%",
    hint: "from last month",
    icon: Users,
  },
  {
    title: "Sales",
    value: "+12,234",
    change: "+19%",
    hint: "from last month",
    icon: CreditCard,
  },
  {
    title: "Active Now",
    value: "+573",
    change: "+201",
    hint: "since last hour",
    icon: Activity,
  },
];

const statusVariant = {
  Paid: "default",
  Processing: "secondary",
  Pending: "outline",
  Refunded: "destructive",
} as const;

const orders = [
  {
    id: "#3210",
    customer: "Olivia Martin",
    email: "olivia@example.com",
    status: "Paid",
    date: "Jun 12, 2026",
    amount: "$1,999.00",
  },
  {
    id: "#3209",
    customer: "Jackson Lee",
    email: "jackson@example.com",
    status: "Processing",
    date: "Jun 12, 2026",
    amount: "$39.00",
  },
  {
    id: "#3208",
    customer: "Isabella Nguyen",
    email: "isabella@example.com",
    status: "Paid",
    date: "Jun 11, 2026",
    amount: "$299.00",
  },
  {
    id: "#3207",
    customer: "William Kim",
    email: "will@example.com",
    status: "Pending",
    date: "Jun 10, 2026",
    amount: "$99.00",
  },
  {
    id: "#3206",
    customer: "Sofia Davis",
    email: "sofia@example.com",
    status: "Refunded",
    date: "Jun 09, 2026",
    amount: "$39.00",
  },
  {
    id: "#3205",
    customer: "Liam Johnson",
    email: "liam@example.com",
    status: "Paid",
    date: "Jun 08, 2026",
    amount: "$799.00",
  },
];

export default function DashboardPage() {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader>
              <CardDescription>{stat.title}</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {stat.value}
              </CardTitle>
              <CardAction>
                <stat.icon className="size-4 text-muted-foreground" />
              </CardAction>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                <span className="font-medium text-emerald-600 dark:text-emerald-400">
                  {stat.change}
                </span>{" "}
                {stat.hint}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Orders</CardTitle>
          <CardDescription>The latest transactions from your store.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Date</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((order) => (
                <TableRow key={order.id}>
                  <TableCell className="font-medium">{order.id}</TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium">{order.customer}</span>
                      <span className="text-xs text-muted-foreground">
                        {order.email}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        statusVariant[order.status as keyof typeof statusVariant]
                      }
                    >
                      {order.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {order.date}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {order.amount}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
