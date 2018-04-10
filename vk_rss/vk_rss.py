"""
Module creates RSS feeds (XML files) based on the posts from
vk.com groups. One feed for one group.

To use it, type in init_data.txt your login on the first line,
your password on the second line, the path where you want to save
your XML files on the third line, True or False on the 4th line
depending on whether you want reposts in your feeds or not and then
one short name of a group on a line, for example, if the group link
is https://vk.com/club1, then the short name is 'club1' (see init_data.txt).

To run the script, just:
>>> python3 vk_rss.py
"""

import os
from datetime import datetime

from feedgen.feed import FeedGenerator
from tzlocal import get_localzone
from vk_api import AuthError, VkApi, VkApiError


class Attachment():
    """
    Represents a post attachment
    """

    def __init__(self, attach_type, attach_dict):
        self.attach_type = attach_type
        self.attach_dict = attach_dict

    def render(self):
        """
        Decides how to render an attachment and render it
        """

        func_dispatcher = {
            'photo': Attachment._photo_rendering, 'video': Attachment._video_rendering,
            'audio': Attachment._audio_rendering, 'doc': Attachment._doc_rendering,
            'link': Attachment._link_rendering, 'album': Attachment._album_rendering,
            'poll': Attachment._poll_rendering
        }

        return func_dispatcher[self.attach_type](self.attach_dict)

    def _photo_rendering(photo_dict):
        """
        Returns info about rendering a photo attachment

        :param photo_dict: dictionary, looks like {'photo_130': ...,
                           'text': ..., ...}, see VK API
        :returns: string, contain html tags
        """

        # Get the url of the best quality image
        photo_url = (
            photo_dict.get('photo_2560') or photo_dict.get('photo_1280') or
            photo_dict.get('photo_807') or photo_dict.get('photo_604') or
            photo_dict.get('photo_130') or photo_dict.get('photo_75')
        )

        return Attachment._image_tag(photo_url, photo_dict['text'])

    def _video_rendering(video_dict):
        """
        Returns info about rendering a video attachment

        :param video_dict: dictionary, looks like {'photo_130': ...,
                           'title': ..., ...}, see VK API

        :returns: string, contain html tags
        """

        # Get the url of the best quality image
        photo_url = (
            video_dict.get('photo_800') or video_dict.get('photo_640') or
            video_dict.get('photo_320') or video_dict.get('photo_130')
        )

        return Attachment._image_tag(photo_url, video_dict['title'] + ' [Video]')

    def _audio_rendering(audio_dict):
        """
        Returns info about rendering an audio attachment

        :param audio_dict: dictionary, looks like {'artist': ...,
                           'title': ..., ...}, see VK API
        :returns: string, contain html tags
        """

        audio_tag = '<a href="{}">{} - {} [Audio]</a>'.format(
            audio_dict['url'],
            audio_dict['artist'],
            audio_dict['title']
        )

        return audio_tag

    def _doc_rendering(doc_dict):
        """
        Returns info about rendering a doc attachment

        :param doc_dict: dictionary, looks like {'size': ...,
                           'title': ..., ...}, see VK API
        :returns: string, contain html tags
        """

        # It's a .gif
        if doc_dict['type'] == 3:
            doc_tag = Attachment._image_tag(doc_dict['url'], doc_dict['title'])
        else:
            doc_tag = '<a href="{}">{} - {:.2f}MB [Doc]</a>'.format(
                doc_dict['url'],
                doc_dict['title'],
                doc_dict['size'] / 1024**2
            )

        return doc_tag

    def _link_rendering(link_dict):
        """
        Returns info about rendering a link attachment

        :param link_dict: dictionary, looks like {'url': ...,
                           'title': ..., ...}, see VK API
        :returns: string, contain html tags
        """

        preview = link_dict.get('photo')
        preview_tag = ''
        if preview:
            preview_tag = Attachment._photo_rendering(preview).split('<p>')[0]

        link_tag = '<a href="{}">{}<p>{} [Link]</p></a>'.format(
            link_dict['url'],
            preview_tag,
            link_dict['title']
        )

        return link_tag

    def _album_rendering(album_dict):
        """
        Returns info about rendering an album attachment

        :param album_dict: dictionary, looks like {'thumb': ...,
                           'title': ..., ...}, see VK API
        :returns: string, contain html tags
        """

        thumb_tag = Attachment._photo_rendering(album_dict['thumb']).split('<p>')
        album_tag = thumb_tag[0] + '<p>{} [Album]</p>'.format(album_dict['title'])

        return album_tag

    def _poll_rendering(poll_dict):
        """
        Returns info about rendering a poll attachment

        :param poll_dict: dictionary, looks like {'votes': ...,
                           'question': ..., ...}, see VK API
        :returns: string, contain html tags
        """

        poll_lines = []
        poll_lines.append('Pole: {}'.format(poll_dict['question']))
        poll_lines.append('-' * 30)
        for ans in poll_dict['answers']:
            poll_lines.append('{} -- {}'.format(ans['text'], ans['rate']))
        poll_lines.append('-' * 30)
        poll_lines.append('Number of votes: {}'.format(poll_dict['votes']))

        return '<br>'.join(poll_lines)

    def _image_tag(url, description):
        """Returns html tags for an image and its description"""
        return '<img src="{}"><p>{}</p>'.format(url, description)


def not_rendered_element_tag(element_type):
    """Returns html tag for an element we do not want to render"""
    return '<strong>You can find {} in the post</strong>'.format(element_type)

def description_post(post):
    """
    Form RSS item description based on the information
    from a post

    :param post: a dictionary representing data of the post we
           get with vk_api lib, in fact, it's an element of
           api.wall.get(...)['items'] list
    :returns: string, description of a RSS item
    """

    attachment_tags = []
    not_rendered_elms = {
        t: 0 for t in ['photos_list', 'comments', 'note', 'page',
                       'market', 'market_album', 'sticker']
    }

    # Go through the attachments and form what every
    # attachment should look like in the feed
    for att in post.get('attachments', []):
        # Elements we do not want to render but want to
        # know about
        att_type = att['type']
        if att_type in not_rendered_elms:
            not_rendered_elms[att_type] = 1
            continue

        att_obj = Attachment(att_type, att[att_type])
        attachment_tags.append(att_obj.render())

    # If the post is a repost, post['copy_history'] does not have
    # 'comments' key. So it may have comments but I do not need them
    comments = post.get('comments', {'count': 0})
    if comments['count']:
        not_rendered_elms['comments'] = 1

    # Collect info about not rendered elements (so we know
    # they are in the post and we can go to see them if we want to)
    for elm in not_rendered_elms:
        if not_rendered_elms[elm]:
            attachment_tags.append(not_rendered_element_tag(elm))

    # To render new lines adequately
    post_text = '<br>'.join((post['text'].split('\n'))) + '<br>'

    return post_text + '<br>'.join(attachment_tags)

def post_parsing(post, group_name):
    """
    Go through the dictionary containing :post: data
    and make a new dictionary to create an RSS item

    :param post: a dictionary representing data of the post we
           get with vk_api lib, in fact, it's an element of
           api.wall.get(...)['items'] list;
    :param group_name: string, the name of the group we make
                 RSS feed for
    :returns: a dictionary to create an RSS item
    """

    # post_data keys correspond to RSS specification
    post_data = {}
    # If there's text in the post, use the first 20
    # characters for the RSS item title
    if post['text']:
        post_data['title'] = post['text'][:20] + '...'
    # If not, use the name of the group
    else:
        post_data['title'] = group_name

    post_data['link'] = 'https://vk.com/wall{}_{}'.format(post['from_id'], post['id'])
    post_data['description'] = description_post(post)
    post_data['guid'] = '{}_{}'.format(post['from_id'], post['id'])
    local_tz = get_localzone()
    post_data['pubDate'] = datetime.fromtimestamp(post['date'], tz=local_tz)

    return post_data

def rss_feed_for_group(api, group, reposts=True):
    """
    Create rss feed based on the group posts

    :param api: VkApiMethod instance, to initialise it,
          api = vk_api.VkApi(USERNAME, PASSWORD).get_api();
    :param group: string, short name of a group, for instance,
            'club1' in https://vk.com/club1/;
    :param reposts: boolean, False if we do not want to add reposts
              to the feed
    :returns: FeedGenerator instance, ready for writing XML
    """

    # VK API allows to make 10000 calls per day with wall.get_localzone
    # so if we going to refresh a feed every 20 minutes (it's 72 a day),
    # we should be ok with about 138 groups (if I get it right)

    # Get the first 60 (should be enough) posts from a group
    vargs = {'domain': group, 'count': 60}

    # If a group doesn't have a short name, its url looks like,
    # for example, this: vk.com/club526452694, but, in general, a group
    # can have a short name beginning with 'club'. The problem is that
    # VK API doesn't allow to get the posts from the group 'club526452694'
    # if we use it as the short name (it returns an empty list) therefore
    # we have to check it
    if group[:4] == 'club':
        # So if it's a shortname beginning with 'club', we get an exception
        try:
            owner_id = -1 * int(group[4:])
            vargs['owner_id'] = owner_id
            del vargs['domain']
        except ValueError:
            pass

    try:
        posts = api.wall.get(**vargs)['items']
        # Get the name of a group
        group_name = api.groups.getById(group_id=group)[0]['name']
    except VkApiError as error_msg:
        print(error_msg)

    # Generate the feed
    fg = FeedGenerator()
    fg.title(group_name)
    fg.link(href='https://vk.com/{}/'.format(group))
    fg.description("Vk feed - {}".format(group_name))
    # Get the local timezone odject
    local_tz = get_localzone()
    # Feedgen lib desperatly want timezone info in every date
    fg.lastBuildDate(datetime.now(local_tz))

    # Go through the posts...
    for post in posts:
        # We do not need ads, right?
        if post['marked_as_ads']:
            continue
        # If the post is not a repost
        if post.get('copy_history') is None:
            post_data = post_parsing(post, group_name)
        # If it is, pass to post_parsing function the dictionary
        # post['copy_history'][0] representing the post
        # which the repost are made from (if we want reposts)
        elif reposts:
            post_data = post_parsing(post['copy_history'][0], group_name)
        else:
            continue

        # ...and create RSS items
        fe = fg.add_entry()
        fe.title(post_data['title'])
        fe.link(href=post_data['link'])
        fe.description(post_data['description'])
        fe.guid(post_data['guid'])
        fe.pubdate(post_data['pubDate'])

    return fg


if __name__ == '__main__':

    # Read user data, path and groups' names
    with open('init_data.txt', encoding='utf-8') as f:
        USERNAME, PASSWORD, PATH_TO_SAVE_XML, REPOSTS = [
            f.readline().rstrip() for _ in range(4)
        ]

        GROUPS = [line.rstrip() for line in f if line != '']

    # Initialise connection
    try:
        vk_session = VkApi(USERNAME, PASSWORD)
        vk_session.auth()
    except AuthError as error_msg:
        print(error_msg)

    # Get VkApiMethod that allows using Vk API
    # like this: api.wall.get(...) or api.groups.getById(...)
    api = vk_session.get_api()

    # Create dir for XML files
    if not os.path.exists(PATH_TO_SAVE_XML):
        os.makedirs(PATH_TO_SAVE_XML)

    # Go through the groups
    for group in GROUPS:
        if REPOSTS.lower() == 'true':
            fg = rss_feed_for_group(api, group)
        else:
            fg = rss_feed_for_group(api, group, reposts=False)
        # Write .xml file
        xml_name = PATH_TO_SAVE_XML + '\\vk_feed_{}.xml'.format(group)
        fg.rss_file(xml_name)

    print('XML files have been created.')
