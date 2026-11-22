export const store = {
    currentUser: null,
    problems: [],
    submissions: [],
    tags: [],

    setUser(user) {
        this.currentUser = user;
    },

    clearUser() {
        this.currentUser = null;
    },

    isLoggedIn() {
        return !!this.currentUser;
    },

    isAdmin() {
        return !!(this.currentUser && this.currentUser.isAdmin);
    },
};