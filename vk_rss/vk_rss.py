"""Module create RSS feeds based on the posts from vk.com groups.
One feed for one group.

To use it, type in init_data.txt your login on the first line,
your password on the second line and then one short name of a group
on a line, for example, if the group link is https://vk.com/club1,
then the short name is 'club1' (see init_data.txt).

To run the script, just:
>>> python3 vk_rss.py
"""

from datetime import datetime

from feedgen.feed import FeedGenerator
from pytz import timezone
from vk_api import AuthError, VkApi, VkApiError


def image_tag(url, description):
    """Return html tag for an image and its description"""
    return '<img src="{}"><p>{}</p>'.format(url, description)

def not_rendered_element_tag(element_type):
    """Return html tag for an element we do not want to render"""
    return '<strong>There is {} element in the post</strong>'.format(element_type)

def description_post(post):
    """Form RSS item description based on the information
    from a post

    Parameters:
    -----------
    :post: a dictionary representing data of the post we
           get with vk_api lib, in fact, it's an element of
           api.wall.get(...)['items'] list

    Returns:
    -----------
    :description: string, description of a RSS item
    """

    attachment_tags = []
    # Go through the attachments and form
    # how every attachment should look in the feed
    for att in post['attachments']:
        if att['type'] == 'photo':
            # Get the url of the best quality image
            photo_url = (
                att['photo'].get('photo_2560') or att['photo'].get('photo_1280') or
                att['photo'].get('photo_807') or att['photo'].get('photo_604') or
                att['photo'].get('photo_130') or att['photo'].get('photo_75')
            )
            attachment_tags.append(image_tag(photo_url, att['photo']['text']))

        if att['type'] == 'video':
            photo_url = (
                att['video'].get('photo_800') or att['video'].get('photo_640') or
                att['video'].get('photo_320') or att['video'].get('photo_130')
            )
            # We know that there's a video in the post so we can go there if
            # we want to watch it
            attachment_tags.append(not_rendered_element_tag(att['type']))
            attachment_tags.append(image_tag(photo_url, att['video']['title']))

        # The same thing as for videos
        if att['type'] in {'audio', 'doc', 'link', 'album', 'photos_list'}:
            attachment_tags.append(not_rendered_element_tag(att['type']))

        # If the post is a repost, post['copy_history'] does not have
        # 'comments' key. So it may have comments but I do not need them
        comments = post.get('comments', {'count': 0})
        if comments['count'] != 0:
            attachment_tags.append('<strong>There are comments in the post</strong>')

    # To render new lines adequately
    post_text = '<br>'.join((post['text'].split('\n'))) + '<br>'
    descrition = post_text + '<br>'.join(attachment_tags)

    return descrition

def post_parsing(post, group_name):
    """Go through the dictionary containing :post: data
    and make a new dictionary to create an RSS item

    Parameters:
    -----------
    :post: a dictionary representing data of the post we
           get with vk_api lib, in fact, it's an element of
           api.wall.get(...)['items'] list;
    :group_name: string, the name of the group we make
                 RSS feed for

    Returns:
    -----------
    :post_data: a dictionary to create an RSS item
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
    post_data['pubDate'] = datetime.fromtimestamp(
        post['date'],
        tz=timezone('Europe/Moscow')
    )
    '''.strftime('%Y%m%d%H%M')
    post_data['pubDate'] = datetime.datetime(
        int(date[:4]), int(date[4:6]), int(date[6:8]),
        int(date[8:10]), int(date[10:]),
        tzinfo=timezone('Europe/Moscow')
    )'''

    return post_data

def rss_feed_from_group(api, group):
    """Create rss feed based on the group posts

    Parameters:
    -----------
    :api: VkApiMethod instance, to initialise it,
          api = vk_api.VkApi(USERNAME, PASSWORD).get_api();
    :group: string, short name of a group, for instance,
            'club1' in https://vk.com/club1/
    """

    try:
        # Get the first 20 posts from a group
        posts = api.wall.get(domain=group, count=20)['items']
        # Get the name of a group
        group_name = api.groups.getById(group_id=group)[0]['name']
    except VkApiError as error_msg:
        print(error_msg)

    # Generate the feed
    fg = FeedGenerator()
    fg.title(group_name)
    fg.link(href='https://vk.com/{}/'.format(group))
    fg.description("Vk feed - {}".format(group_name))
    # Feedgen lib desperatly want timezone info in every date
    fg.lastBuildDate(datetime.now(timezone('Europe/Moscow')))

    # Go through the posts...
    for post in posts:
        # If the post is not a repost
        if post.get('copy_history') is None:
            post_data = post_parsing(post, group_name)
        # If it is, pass to post_parsing function the dictionary
        # post['copy_history'][0] representing the post
        # which the repost are made from
        else:
            post_data = post_parsing(post['copy_history'][0], group_name)

        # ...and create RSS items
        fe = fg.add_entry()
        fe.title(post_data['title'])
        fe.link(href=post_data['link'])
        fe.description(post_data['description'])
        fe.guid(post_data['guid'])
        fe.pubdate(post_data['pubDate'])

    # Write .xml file
    fg.rss_file('vk_feed_{}.xml'.format(group))


if __name__ == '__main__':

    # Read user data and groups' names
    with open('init_data.txt') as f:
        USERNAME = f.readline().rstrip()
        PASSWORD = f.readline().rstrip()

        GROUPS = [line.rstrip() for line in f]

    # Initialise connection
    try:
        vk_session = VkApi(USERNAME, PASSWORD)
        vk_session.auth()
    except AuthError as error_msg:
        print(error_msg)

    # Get VkApiMethod that allows using Vk API
    # like this: api.wall.get(...) or api.groups.getById(...)
    api = vk_session.get_api()

    # Go through the groups
    for group in GROUPS:
        rss_feed_from_group(api, group)

    print('XML files have been created.')
