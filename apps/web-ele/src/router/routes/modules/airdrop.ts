import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:package',
      order: 10,
      title: '空投包管理',
    },
    name: 'Airdrop',
    path: '/airdrop',
    children: [
      {
        name: 'AirdropPacks',
        path: '/airdrop/packs',
        component: () => import('#/views/airdrop/index.vue'),
        meta: {
          icon: 'lucide:search',
          title: '空投包检索',
        },
      },
    ],
  },
];

export default routes;
