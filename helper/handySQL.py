import sqlite3
from sqlite3 import Error
import random
import re


def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)
    return conn


def create_table(conn, create_table_sql):
    """
    Creates a table
    :param conn:
    :param create_table_sql:
    :return:
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        conn.commit()
    except Error as e:
        print(e)


def update_voice(conn, UniqueMemberID):
    try:
        rand_amount = random.randrange(1, 10)
        sql = f"""UPDATE VoiceLevels SET ExperienceAmount = ExperienceAmount + {rand_amount} WHERE UniqueMemberID=?"""
        c = conn.cursor()
        c.execute(sql, [UniqueMemberID])
        conn.commit()
    except Error as e:
        print(e)


def get_uniqueMemberID(conn, DiscordUserID, DiscordGuildID):
    try:
        c = conn.cursor()
        c.execute("SELECT UniqueMemberID FROM DiscordMembers WHERE DiscordUserID=? AND DiscordGuildID=?", (DiscordUserID, DiscordGuildID))
        rows = c.fetchone()
        if rows is not None:
            return rows[0]
        return -1
    except Error as e:
        print(e)


def get_DiscordUserID(conn, uniqueID):
    try:
        c = conn.cursor()
        c.execute("SELECT DiscordUserID FROM DiscordMembers WHERE UniqueMemberID=?", (uniqueID,))
        rows = c.fetchone()
        if rows is not None:
            return rows[0]
    except Error as e:
        print(e)


def insert(conn, values, value_identifier, table):
    """
    Creates a new row in the given table
    :param conn:
    :param values:
    :param value_identifier:
    :param table:
    :return: Dictionary with RowCount and LastRowID or None if there was an error
    """
    if len(values) != len(value_identifier):
        print("ERROR! Values and Value identifiers length don't match up")
        return
    try:
        # Formats the value identifiers to fit
        formatted_identifiers = ", ".join(value_identifier)
        question_marks = ""
        for i in range(len(values)):
            question_marks += "?"
            if i < len(values)-1:
                question_marks += ","
        sql = f"""INSERT INTO {table}({formatted_identifiers}) VALUES ({question_marks})"""
        c = conn.cursor()
        c.execute(sql, values)
        conn.commit()
        print(f"Table: {table} | Rows changed: {c.rowcount}")
        return True, c.rowcount
    except Error as e:
        return False, e


def update(conn, values, value_identifier, table):
    if len(values) != len(value_identifier):
        print("ERROR! Values and Value identifiers length don't match up")
        return
    try:
        # Formats the value identifiers to fit
        formatted_identifiers = ""
        for v in range(len(value_identifier)):
            formatted_identifiers += value_identifier[v] + "=?"
            if v < len(values) - 1:
                formatted_identifiers += ","
        sql = f"""UPDATE {table} SET {formatted_identifiers}"""
        c = conn.cursor()
        c.execute(sql, values)
        conn.commit()
    except Error as e:
        return False, e


def create_discord_user(conn, DiscordUserID, DisplayName, Discriminator, IsBot, AvatarURL=None, CreatedAt=None):
    """
    Creates a user entry in the DiscordUsers table
    :param conn:
    :param DiscordUserID:
    :param DisplayName:
    :param Discriminator:
    :param IsBot:
    :param AvatarURL:
    :param CreatedAt:
    :return: Dictionary with RowCount and LastRowID or None if there was an error
    """
    values = (DiscordUserID, DisplayName, Discriminator, IsBot, str(AvatarURL), str(CreatedAt))
    value_identifier = ("DiscordUserID", "DisplayName", "Discriminator", "IsBot", "AvatarURL", "CreatedAt")
    return insert(conn, values, value_identifier, "DiscordUsers")


def create_discord_guild(conn, DiscordGuildID, GuildName, GuildRegion, GuildChannelCount, GuildMemberCount, GuildRoleCount):
    """
    Creates a guild entry in the DiscordGuilds table
    :return: Dictionary with RowCount and LastRowID or None if there was an error
    """
    values = (DiscordGuildID, GuildName, GuildRegion, GuildChannelCount, GuildMemberCount, GuildRoleCount)
    value_identifier = ("DiscordGuildID", "GuildName", "GuildRegion", "GuildChannelCount", "GuildMemberCount", "GuildRoleCount")
    return insert(conn, values, value_identifier, "DiscordGuilds")


def create_discord_channel(conn, ChannelObject):
    """
    Creates a channel entry
    :return: Dictionary with RowCount and LastRowID or None if there was an error
    """
    try:
        guild_id = ChannelObject.guild.id
        name = ChannelObject.name
        position = ChannelObject.position
    except AttributeError:
        guild_id = 0
        name = "Direct Message Channel"
        position = 0
    values = (ChannelObject.id, guild_id, name, str(ChannelObject.type), position)
    value_identifier = ("DiscordChannelID", "DiscordGuildID", "ChannelName", "ChannelType", "ChannelPosition")
    return insert(conn, values, value_identifier, "DiscordChannels")


def fix_guild(GuildObject):
    if GuildObject is None:
        guild_id = 0
        guild_name = "Private Channel"
        guild_region = None
        guild_channel_count = None
        guild_member_count = None
        guild_role_count = None
    else:
        guild_id = GuildObject.id
        guild_name = GuildObject.name
        guild_region = str(GuildObject.region)
        guild_channel_count = len(GuildObject.channels)
        guild_member_count = GuildObject.member_count
        guild_role_count = len(GuildObject.roles)
    return guild_id, guild_name, guild_region, guild_channel_count, guild_member_count, guild_role_count


def fix_channel(ChannelObject):
    try:
        id = ChannelObject.id
        name = ChannelObject.name
        type = str(ChannelObject.type)
        position = ChannelObject.position
    except AttributeError:
        id = ChannelObject.id
        name = "Private Message Channel"
        type = str(ChannelObject.type)
        position = 0
    return id, name, type, position


def create_discord_member(conn, MemberObject, GuildObject):
    isBot = 0
    if MemberObject.bot:
        isBot = 1
    create_discord_user(conn, MemberObject.id, MemberObject.name, MemberObject.discriminator, isBot, MemberObject.avatar_url, MemberObject.created_at)
    guild_id, guild_name, guild_region, guild_channel_count, guild_member_count, guild_role_count = fix_guild(GuildObject)
    create_discord_guild(conn, guild_id, guild_name, guild_region, guild_channel_count, guild_member_count, guild_role_count)
    try:
        joinedAt = MemberObject.joined_at
        nick = MemberObject.nick
    except AttributeError:
        joinedAt = None
        nick = None
    create_simple_discord_member(conn, MemberObject.id, guild_id, joinedAt, nick)


def create_simple_discord_member(conn, DiscordUserID, DiscordGuildID, JoinedAt=None, Nickname=None, Semester=None):
    """
    Creates a member entry in the DiscordMembers table
    :return: Dictionary with RowCount and LastRowID or None if there was an error
    """
    # Check if the member already exists
    c = conn.cursor()
    sql = """SELECT DiscordUserID, DiscordGuildID FROM DiscordMembers WHERE DiscordUserID=? AND DiscordGuildID=?"""
    c.execute(sql, (DiscordUserID, DiscordGuildID))
    result = c.fetchone()
    if result is not None:
        uniqueID = get_uniqueMemberID(conn, DiscordUserID, DiscordGuildID)
        if uniqueID is not None:
            c.execute("UPDATE DiscordMembers SET JoinedAt=?, Nickname=?, Semester=? WHERE UniqueMemberID=?", (JoinedAt, Nickname, Semester, uniqueID))
            conn.commit()
        return

    values = (DiscordUserID, DiscordGuildID, JoinedAt, Nickname, Semester)
    value_identifier = ("DiscordUserID", "DiscordGuildID", "JoinedAt", "Nickname", "Semester")
    return insert(conn, values, value_identifier, "DiscordMembers")


def create_voice_level_entry(conn, MemberObject, GuildObject):
    """
    Creates DiscordMember and VoiceLevel entries using Discord objects
    :param conn:
    :param MemberObject:
    :param GuildObject:
    :return:
    """
    if GuildObject is None:
        guild_id = 0
    else:
        guild_id = GuildObject.id
    uniqueID = get_or_create_member(conn, MemberObject, GuildObject)
    return insert(conn, (uniqueID,), ("UniqueMemberID",), "VoiceLevels")


def get_or_create_member(conn, user, guild):
    if guild is None:
        guild_id = 0
    else:
        guild_id = guild.id
    uniqueID = get_uniqueMemberID(conn, user.id, guild_id)
    if uniqueID == -1:
        create_discord_member(conn, user, guild)
        return get_uniqueMemberID(conn, user.id, guild_id)
    else:
        return uniqueID


def create_covid_guessing_entry(conn, member, guild):
    uniqueID = get_or_create_member(conn, member, guild)
    return insert(conn, (uniqueID,), ("UniqueMemberID",), "CovidGuessing")


def create_message_statistic_entry(conn, user, guild, subjectID, table):
    try:
        c = conn.cursor()
        uniqueID = get_or_create_member(conn, user, guild)
        c.execute(f"SELECT * FROM {table} WHERE UniqueMemberID=? AND SubjectID=?", (uniqueID, subjectID))
        if c.fetchone() is None:
            c.execute(f"INSERT INTO {table}(UniqueMemberID,SubjectID) VALUES (?,?)", (uniqueID, subjectID))
            conn.commit()
            return True, 0, "No Error"  # 0 being no error and entry was created
        else:
            return True, 1, "No Error"  # 1 being the entry already exists, so nothing was done
    except Error as e:
        return False, -1, e


def increment_message_statistic(conn, user, guild, subjectID, statistic, table, amount=1):
    uniqueID = get_or_create_member(conn, user, guild)
    try:
        c = conn.cursor()
        c.execute(f"SELECT * FROM {table} WHERE UniqueMemberID=? AND SubjectID=?", (uniqueID, subjectID))
        if c.fetchone() is None:
            result = create_message_statistic_entry(conn, user, guild, subjectID, table)
            if not result[0]:
                return result[2]
        c.execute(f"UPDATE {table} SET {statistic}={statistic}+? WHERE UniqueMemberID=? AND SubjectID=?", (amount, uniqueID, subjectID))
        conn.commit()
        return True, 0, "No Error"
    except Error as e:
        return False, -1, e


def open_file(file_name):
    with open(file_name, "r", encoding="utf8") as f:
        word_file = f.read()
        word_file = re.sub(r'\([^)]*\)', '', word_file)
        word_file = re.findall(r"[\w']+", word_file)
    return word_file


def dictionary_to_db():
    conn = create_connection("../data/discord.db")
    c = conn.cursor()
    dictionaries = {
        "../data/german.txt": "german",
        "../data/english.txt": "english"
    }
    for dictio in dictionaries.keys():
        lang = dictionaries[dictio]
        count = 0
        word_file = open_file(dictio)
        print(f"Word Count: {len(word_file)}")
        for w in word_file:
            try:
                c.execute("INSERT INTO Dictionary(Word, WordLanguage) VALUES (?,?)", (w, lang))
                count += 1

                if count % 100 == 0:
                    print(f"{lang} | {count}")
            except Error as e:
                print(e)
        conn.commit()


def create_all_tables(path):
    database = path
    sql_create_DiscordUsers = """ CREATE TABLE IF NOT EXISTS DiscordUsers (
                                    DiscordUserID integer NOT NULL PRIMARY KEY,
                                    DisplayName text NOT NULL,
                                    Discriminator integer NOT NULL,
                                    IsBot integer NOT NULL,
                                    AvatarURL text,
                                    CreatedAt text
                                    );"""
    sql_create_DiscordGuilds = """ CREATE TABLE IF NOT EXISTS DiscordGuilds (
                                    DiscordGuildID integer NOT NULL PRIMARY KEY,
                                    GuildName text NOT NULL,
                                    GuildRegion text,
                                    GuildChannelCount integer,
                                    GuildMemberCount integer,
                                    GuildRoleCount integer
                                    );"""
    sql_create_DiscordMembers = """ CREATE TABLE IF NOT EXISTS DiscordMembers (
                                    UniqueMemberID integer PRIMARY KEY,
                                    DiscordUserID integer NOT NULL,
                                    DiscordGuildID integer NOT NULL,
                                    JoinedAt text,
                                    Nickname text,
                                    Semester integer,
                                    FOREIGN KEY (DiscordUserID) REFERENCES DiscordUsers(DiscordUserID),
                                    FOREIGN KEY (DiscordGuildID) REFERENCES DiscordGuilds(DiscordGuildID)
                                    );"""
    sql_create_DiscordChannels = """ CREATE TABLE IF NOT EXISTS DiscordChannels (
                                        DiscordChannelID integer NOT NULL PRIMARY KEY,
                                        DiscordGuildID integer NOT NULL,
                                        ChannelName text,
                                        ChannelType text,
                                        ChannelPosition integer,
                                        FOREIGN KEY (DiscordGuildID) REFERENCES DiscordGuilds(DiscordGuildID)
                                        );"""
    sql_create_Subject = """ CREATE TABLE IF NOT EXISTS Subject (
                            SubjectID integer NOT NULL PRIMARY KEY,
                            SubjectName text,
                            SubjectAbbreviation text,
                            SubjectSemester integer
                            );"""
    sql_create_WeekDayTimes = """ CREATE TABLE IF NOT EXISTS WeekDayTimes (
                                UniqueDayTimesID integer NOT NULL PRIMARY KEY,
                                SubjectID integer NOT NULL,
                                DayID integer NOT NULL,
                                TimeFrom integer,
                                TimeTo integer,
                                StreamLink text,
                                OnSiteLocation text,
                                FOREIGN KEY (SubjectID) REFERENCES Subject(SubjectID)
                                );"""
    sql_create_UserReactionStatistic = """ CREATE TABLE IF NOT EXISTS UserReactionStatistic (
                                                UserReactionStatisticID integer NOT NULL PRIMARY KEY,
                                                SubjectID integer NOT NULL,
                                                UniqueMemberID integer NOT NULL,
                                                ReactionAddedCount integer DEFAULT 0,
                                                ReactionRemovedCount integer DEFAULT 0,
                                                GottenReactionCount integer DEFAULT 0,
                                                GottenReactionRemovedCount integer DEFAULT 0,
                                                FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID),
                                                FOREIGN KEY (SubjectID) REFERENCES Subject(SubjectID)
                                                );"""
    sql_create_UserMessageStatistic = """ CREATE TABLE IF NOT EXISTS UserMessageStatistic (
                                        UserMessageStatisticID integer NOT NULL PRIMARY KEY,
                                        -- stats for each subject, where subjectID 0 is no current subject
                                        SubjectID integer NOT NULL,
                                        UniqueMemberID integer NOT NULL,
                                        MessageSentCount integer DEFAULT 0,
                                        MessageDeletedCount integer DEFAULT 0,
                                        MessageEditedCount integer DEFAULT 0,
                                        CharacterCount integer DEFAULT 0,
                                        WordCount integer DEFAULT 0,
                                        SpoilerCount integer DEFAULT 0,
                                        EmojiCount integer DEFAULT 0,
                                        FileSentCount integer DEFAULT 0,
                                        FileTotalSize integer DEFAULT 0,
                                        ImageCount integer DEFAULT 0,
                                        FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID),
                                        FOREIGN KEY (SubjectID) REFERENCES Subject(SubjectID)
                                        );"""
    sql_create_VoiceLevels = """ CREATE TABLE IF NOT EXISTS VoiceLevels (
                                    UniqueMemberID integer NOT NULL PRIMARY KEY,
                                    ExperienceAmount integer DEFAULT 0,
                                    FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                                    );"""
    sql_create_CovidGuessing = """  CREATE TABLE IF NOT EXISTS CovidGuessing (
                                    UniqueMemberID integer NOT NULL PRIMARY KEY,
                                    TotalPointsAmount integer DEFAULT 0,
                                    GuessCount integer DEFAULT 0,
                                    NextGuess integer,
                                    TempPoints integer,
                                    FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                                    );"""
    sql_create_reputations = """    CREATE TABLE IF NOT EXISTS Reputations (
                                    ReputationID integer NOT NULL PRIMARY KEY,
                                    UniqueMemberID integer NOT NULL,
                                    ReputationMessage text,
                                    CreatedAt text,
                                    AddedByUniqueMemberID integer,
                                    IsPositive integer,
                                    FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID),
                                    FOREIGN KEY (AddedByUniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                                    );"""
    sql_create_events = """     CREATE TABLE IF NOT EXISTS Events (
                                        EventID integer PRIMARY KEY,
                                        EventName text NOT NULL,
                                        EventCreatedAt text,
                                        EventStartingAt text,
                                        EventDescription text,
                                        UniqueMemberID integer,
                                        UpdatedMessageID integer,
                                        UpdatedChannelID integer,
                                        IsDone integer,
                                        FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                                        );"""

    sql_create_eventjoinedusers = """   CREATE TABLE IF NOT EXISTS "EventJoinedUsers" (
                                        "EventJoinedID"	INTEGER,
                                        "EventID"	INTEGER,
                                        "UniqueMemberID"	INTEGER,
                                        "JoinedAt"	TEXT DEFAULT CURRENT_TIMESTAMP,
                                        "IsHost"	INTEGER DEFAULT 0,
                                        FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers"("UniqueMemberID"),
                                        PRIMARY KEY("EventJoinedID"),
                                        FOREIGN KEY("EventID") REFERENCES "Events"("EventID") ON DELETE CASCADE
                                        );"""
    sql_create_quotes = """   CREATE TABLE IF NOT EXISTS "Quotes" (
                                        "QuoteID" INTEGER PRIMARY KEY,
                                        "Quote" INTEGER,
                                        "Name" TEXT, -- name of who the quote is from
                                        "UniqueMemberID" INTEGER, -- uniqueID if it exists
                                        "CreatedAt"	TEXT DEFAULT CURRENT_TIMESTAMP,
                                        "AddedByUniqueMemberID" INTEGER,
                                        "DiscordGuildID" INTEGER,
                                        FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers"("UniqueMemberID"),
                                        FOREIGN KEY("DiscordGuildID") REFERENCES "DiscordGuilds"("DiscordGuildID")
                                        );"""
    sql_create_quote_aliases = """  CREATE TABLE IF NOT EXISTS "QuoteAliases" (
                                        "AliasID" INTEGER PRIMARY KEY,
                                        "NameFrom" TEXT,
                                        "NameTo" TEXT
                                        );"""
    sql_create_config = """   CREATE TABLE IF NOT EXISTS "Config" (
                                        "ConfigID" INTEGER PRIMARY KEY,
                                        "ConfigKey" TEXT,
                                        "ConfigValue" INTEGER
                                        );"""
    sql_create_quotestoremove = """   CREATE TABLE IF NOT EXISTS "QuotesToRemove" (
                                        "QuoteID" INTEGER PRIMARY KEY,
                                        "ReporterID" INTEGER
                                        );"""

    conn = create_connection(database)

    if conn is not None:
        create_table(conn, sql_create_DiscordGuilds)
        create_table(conn, sql_create_DiscordUsers)
        create_table(conn, sql_create_DiscordMembers)
        create_table(conn, sql_create_DiscordChannels)
        create_table(conn, sql_create_Subject)
        create_table(conn, sql_create_WeekDayTimes)
        create_table(conn, sql_create_UserReactionStatistic)
        create_table(conn, sql_create_UserMessageStatistic)
        create_table(conn, sql_create_VoiceLevels)
        create_table(conn, sql_create_CovidGuessing)
        create_table(conn, sql_create_reputations)
        create_table(conn, sql_create_events)
        create_table(conn, sql_create_eventjoinedusers)
        create_table(conn, sql_create_quotes)
        create_table(conn, sql_create_config)
        create_table(conn, sql_create_quote_aliases)
        create_table(conn, sql_create_quotestoremove)

        conn.close()
    else:
        print("ERROR! Cannot connect to database!")


def main():
    create_all_tables("../data/discord.db")


if __name__ == "__main__":
    main()
