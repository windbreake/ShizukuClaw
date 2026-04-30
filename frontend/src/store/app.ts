import { defineStore } from "pinia";

export const useAppStore = defineStore("app", {
  state: () => ({
    counter: 0
  }),
  actions: {
    increment() {
      this.counter += 1;
    }
  }
});
