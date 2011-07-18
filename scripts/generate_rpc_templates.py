#!/usr/bin/env python
import sys

"""This script is used to generate the mailbox templates in
src/rpc/rpc.hpp. It is meant to be run as follows (assuming that the
current directory is rethinkdb/src/):

$ ../scripts/generate_rpc_templates.py > rpc/rpc.hpp

"""

def generate_async_message_template(nargs):

    args = ", ".join("const arg%d_t &arg%d" % (i, i) for i in xrange(nargs))

    print "template<%s>" % ", ".join("class arg%d_t" % i for i in xrange(nargs))
    print "class async_mailbox_t< void(%s) > : private cluster_mailbox_t {" % \
        ", ".join("arg%d_t" % i for i in xrange(nargs))
    print
    print "public:"
    print "    async_mailbox_t(const boost::function< void(%s) > &fun) :" % args
    print "        callback(fun) { }"
    print
    print "    struct address_t {"
    print "        address_t() { }"
    print "        address_t(const address_t &other) : addr(other.addr) { }"
    print "        address_t(async_mailbox_t *mb) : addr(mb) { }"
    print "        void call(%s) {" % args
    if nargs > 0:
        print "            message_t m(%s);" % ", ".join("arg%d" % i for i in xrange(nargs));
    else:
        print "            message_t m;"
    print "            try { addr.send(&m); }"
    print "            catch (tcp_conn_t::write_closed_exc_t) {"
    print "                throw rpc_peer_killed_exc_t();"
    print "            } catch (cluster_peer_t::write_peer_killed_exc_t) {"
    print "                throw rpc_peer_killed_exc_t();"
    print "            }"
    print "        }"
    print "        RDB_MAKE_ME_SERIALIZABLE_1(addr)"
    # print "    private:"    # Make public temporarily
    print "        cluster_address_t addr;"
    print "      public:"
    print "        bool same_as(const address_t &other_addr) {"
    print "            return (addr.mailbox == other_addr.addr.mailbox && addr.peer == other_addr.addr.peer);"
    print "        }"
    print "    };"
    print "    friend class address_t;"
    print
    print "private:"
    print "    struct message_t : public cluster_message_t {"
    print "        message_t(%s)" % args
    if nargs > 0:
        print "            : %s { }" % ", ".join("arg%d(arg%d)" % (i,i) for i in xrange(nargs))
    else:
        print "            { }"
    for i in xrange(nargs):
        print "        const arg%d_t &arg%d;" % (i, i)
    if nargs > 0:
        print "        void serialize(cluster_outpipe_t *pipe) const {"
    else:
        print "        void serialize(UNUSED cluster_outpipe_t *pipe) const {"
    print "            fprintf(stderr, \"serialize in message_t\\n\");"
    for i in xrange(nargs):
        print "            pipe->get_archive() << arg%d;" % i
    print "        }"
    print "    };"
    print "#ifndef NDEBUG"
    print "     const std::type_info& expected_type() {"
    print "         return typeid(message_t);"
    print "     }"
    print "#endif"
    print "    void unserialize(%srpc_iarchive_t &ar, boost::function<void()> done) {" % ("UNUSED " if nargs == 0 else "")
    for i in xrange(nargs):
        print "        arg%d_t arg%d;" % (i, i)
        print "        ar >> arg%d;" % i
    print "        done();"
    print "        callback(%s);" % ", ".join("arg%d" % i for i in xrange(nargs))
    print "    }"
    print
    print "    boost::function< void(%s) > callback;" % args
    if nargs > 0:
        print "    void run(cluster_message_t *cm) {"
    else:
        print "    void run(UNUSED cluster_message_t *cm) {"
    if nargs:
        print "        message_t *m = static_cast<message_t *>(cm);"
    for i in xrange(nargs):
        # Copy each parameter from the message onto the stack because it might become invalid once
        # we call coro_t::wait(), and we would rather not make 'callback' worry about that.
        print "        arg%d_t arg%d(m->arg%d);" % (i, i, i)
    print "        callback(%s);" % ", ".join("arg%d" % i for i in xrange(nargs))
    print "    }"
    print "};"
    print

def generate_sync_message_template(nargs, void):

    args = ", ".join("const arg%d_t &arg%d" % (i, i) for i in xrange(nargs))
    ret = "ret_t" if not void else "void"

    if void:
        print "template<%s>" % ", ".join("class arg%d_t" % i for i in xrange(nargs))
    else:
        print "template<%s>" % ", ".join(["class ret_t"] + ["class arg%d_t" % i for i in xrange(nargs)])
    print "class sync_mailbox_t< %s(%s) > : private cluster_mailbox_t {" % \
        (ret, ", ".join("arg%d_t" % i for i in xrange(nargs)))
    print
    print "public:"
    print "    sync_mailbox_t(const boost::function< %s(%s) > &fun) :" % (ret, args)
    print "        callback(fun) { }"
    print
    print "    struct address_t {"
    print "        address_t() { }"
    print "        address_t(const address_t &other) : addr(other.addr) { }"
    print "        address_t(sync_mailbox_t *mb) : addr(mb) { }"
    print "        %s call(%s) {" % (ret, args)
    if nargs > 0:
        print "            call_message_t m(%s);" % ", ".join("arg%d" % i for i in xrange(nargs));
    else:
        print "            call_message_t m;"
    #print "            struct : public cluster_mailbox_t, public %s, public cluster_peer_t::kill_cb_t {" % ("promise_t<std::pair<bool, ret_t> >" if not void else "promise_t<bool>")
    print "            struct reply_listener_t : public cluster_mailbox_t, public home_thread_mixin_t,"
    print "                     public %s, public cluster_peer_t::kill_cb_t {" % ("promise_t<std::pair<bool, ret_t> >" if not void else "promise_t<bool>")
    print "            private:"
    print "                bool pulsed; //Truly annoying that we need to keep track of this"
    print "            public:"
    print "                reply_listener_t() : pulsed(false) {}"
    print "                void unserialize(%srpc_iarchive_t &ar, boost::function<void()> done) {" % ("UNUSED " if nargs == 0 else "")
    if not void:
        print "                    ret_t ret;"
        print "                    ar >> ret;"
        print "                    done();"
        print "                    on_thread_t syncer(home_thread());"
        print "                    if (pulsed) return;"
        print "                    else pulsed = true;"
        print "                    pulse(std::make_pair(true, ret));"
    else:
        print "                    done();"
        print "                    on_thread_t syncer(home_thread());"
        print "                    if (pulsed) return;"
        print "                    else pulsed = true;"
        print "                    pulse(true);"
    print "                }"
    if not void:
        print "                void run(cluster_message_t *msg) {"
    else:
        print "                void run(UNUSED cluster_message_t *msg) {"
    if not void:
        print "                    ret_message_t *m = static_cast<ret_message_t *>(msg);"
        print "                    ret_t ret = m->ret;"
    print "                    on_thread_t syncer(home_thread());"
    print "                    if (pulsed) return;"
    print "                    else pulsed = true;"
    if not void:
        print "                    pulse(std::make_pair(true, ret));"
    else:
        print "                    pulse(true);"
    print "                }"
    print "#ifndef NDEBUG"
    print "                const std::type_info& expected_type() {"
    print "                    return typeid(ret_message_t);"
    print "                }"
    print "#endif"
    print "                void on_kill() {"
    print "                    on_thread_t syncer(home_thread());"
    print "                    if (pulsed) return;"
    print "                    else pulsed = true;"
    if not void:
        print "                    pulse(std::make_pair(false, ret_t()));"
    else:
        print "                    pulse(false);"
    print "                }"
    print "            } reply_listener;"
    print "            m.reply_to = cluster_address_t(&reply_listener);"
    print "            cluster_t::peer_kill_monitor_t monitor(addr.get_peer(), &reply_listener);"
    print "            try { addr.send(&m); }"
    print "            catch (tcp_conn_t::write_closed_exc_t) {} //This means that the peer was killed but to avoid problems we need to let the reply_listener get pulsed and return the error there."
    print "            catch (cluster_peer_t::write_peer_killed_exc_t) {"
    print "                throw rpc_peer_killed_exc_t();"
    print "            }"
    if not void:
        print "            std::pair<bool, ret_t> res = reply_listener.wait();"
        print "            if (res.first) return res.second;"
        print "            else throw rpc_peer_killed_exc_t();"
    else:
        print "            if (!reply_listener.wait()) throw rpc_peer_killed_exc_t();"
    print "        }"
    print "        RDB_MAKE_ME_SERIALIZABLE_1(addr)"
    print "    private:"
    print "        cluster_address_t addr;"
    print "    public:"
    print "      bool same_as(const address_t &other_addr) {"
    print "          return (addr.mailbox == other_addr.addr.mailbox && addr.peer == other_addr.addr.peer);"
    print "      }"
    print "    };"
    print "    friend class address_t;"
    print
    print "private:"
    print "    struct call_message_t : public cluster_message_t {"
    print "        call_message_t(%s)" % args
    if nargs > 0:
        print "            : %s { }" % ", ".join("arg%d(arg%d)" % (i,i) for i in xrange(nargs))
    else:
        print "            { }"
    for i in xrange(nargs):
        print "        const arg%d_t &arg%d;" % (i, i)
    print "        cluster_address_t reply_to;"
    print "        void serialize(cluster_outpipe_t *pipe) const {"
    print "            fprintf(stderr, \"serialize in call_message_t\\n\");"
    for i in xrange(nargs):
        print "            pipe->get_archive() << arg%d;" % i
    print "            pipe->get_archive() << reply_to;"
    print "        }"
    print "    };"
    print "#ifndef NDEBUG"
    print "     const std::type_info& expected_type() {"
    print "         return typeid(call_message_t);"
    print "     }"
    print "#endif"
    print
    print "    struct ret_message_t : public cluster_message_t {"
    if not void:
        print "        ret_t ret;"
    if not void:
        print "        void serialize(cluster_outpipe_t *pipe) const {"
        print "            pipe->get_archive() << ret;"
    else:
        print "        void serialize(UNUSED cluster_outpipe_t *pipe) const {"
    print "            fprintf(stderr, \"serialize in ret_message_t\\n\");"
    print "        }"
    print "    };"
    print
    print "    boost::function< %s(%s) > callback;" % (ret, args)
    print
    print "    void unserialize(%srpc_iarchive_t &ar, boost::function<void()> done) {" % ("UNUSED " if nargs == 0 else "")
    for i in xrange(nargs):
        print "        arg%d_t arg%d;" % (i, i)
        print "        ar >> arg%d;" % i
    print "        cluster_address_t reply_addr;"
    print "        ar >> reply_addr;"
    print "        done();"
    print "        ret_message_t rm;"
    if not void:
        print "        rm.ret = callback(%s);" % ", ".join("arg%d" % i for i in xrange(nargs))
    else:
        print "        callback(%s);" % ", ".join("arg%d" % i for i in xrange(nargs))
    print "        try { reply_addr.send(&rm); }"
    print "        catch (tcp_conn_t::write_closed_exc_t) {}"
    print "    }"
    print
    print "    void run(cluster_message_t *cm) {"
    print "        call_message_t *m = static_cast<call_message_t *>(cm);"
    print "        ret_message_t rm;"
    if not void:
        print "        rm.ret = callback(%s);" % ", ".join("m->arg%d" % i for i in xrange(nargs))
    else:
        print "        callback(%s);" % ", ".join("m->arg%d" % i for i in xrange(nargs))
    print "        m->reply_to.send(&rm);"
    print "    }"
    print "};"
    print

if __name__ == "__main__":

    print "#ifndef __RPC_RPC_HPP__"
    print "#define __RPC_RPC_HPP__"
    print

    print "/* This file is automatically generated by '%s'." % " ".join(sys.argv)
    print "Please modify '%s' instead of modifying this file.*/" % sys.argv[0]
    print

    print "#include <boost/serialization/serialization.hpp>"
    print "#include \"rpc/serialize/serialize.hpp\""
    print "#include \"rpc/serialize/serialize_macros.hpp\""
    print "#include \"concurrency/cond_var.hpp\""
    print "#include \"concurrency/promise.hpp\""
    print "#include \"rpc/core/cluster.hpp\""
    print "#include \"rpc/core/peer.hpp\""
    print

    print "template<class proto_t> class async_mailbox_t {"
    print "    // BOOST_STATIC_ASSERT(false);"
    print "};"
    print
    print "template<class proto_t> class sync_mailbox_t;"
    print
    print "struct rpc_peer_killed_exc_t : public std::exception {"
    print "    const char *what() throw () {"
    print "        return \"Peer killed during rpc\\n\";"
    print "    }"
    print "};"
    print

    for nargs in xrange(10):
        generate_async_message_template(nargs)
        generate_sync_message_template(nargs, True);
        generate_sync_message_template(nargs, False);

    print
    print "#endif /* __RPC_RPC_HPP__ */"